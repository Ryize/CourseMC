from datetime import datetime, time, timedelta
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import jwt
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

from Course.models import ClassesTimetable, LearnGroup, Student

from .lifecycle import cleanup_closed_rooms, create_due_lessons, end_expired_lessons, sync_lessons
from .media import LiveKitAPIError, room_service
from .models import LiveLesson, LiveLessonReschedule


MOSCOW = ZoneInfo('Europe/Moscow')


def at(day=30, hour=18, minute=0, second=0):
    return datetime(2026, 9, day, hour, minute, second, tzinfo=MOSCOW)


class LessonAutomationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='scheduler-teacher')
        cls.teacher = Student.objects.create(user=cls.user, contact='scheduler', groups_id=719, is_learned=True)
        cls.group = LearnGroup.objects.create(pk=719, title='Группа', teacher=cls.teacher, is_studies=True)
        cls.slot = ClassesTimetable.objects.create(
            group=cls.group, weekday='Среда', time_lesson=time(18), duration=time(1, 30),
        )

    def lesson(self, **fields):
        return LiveLesson.objects.create(**{
            'group': self.group, 'teacher': self.teacher, 'title': 'Урок', 'scheduled_at': at(), **fields,
        })

    def test_exact_five_minutes_not_earlier_and_idempotent(self):
        self.assertEqual(create_due_lessons(at(hour=17, minute=54, second=59)), 0)
        self.assertEqual(create_due_lessons(at(hour=17, minute=55)), 1)
        lesson = LiveLesson.objects.get()
        self.assertEqual(lesson.title, 'Урок')
        self.assertEqual(lesson.duration_minutes, 90)
        self.assertEqual(lesson.scheduled_at, at())
        self.assertEqual(lesson.timetable_date, at().date())
        self.assertEqual(lesson.teacher_id, self.teacher.pk)
        self.assertEqual(lesson.status, LiveLesson.Status.SCHEDULED)
        self.assertTrue(lesson.waiting_room_enabled)
        self.assertEqual(lesson.origin, LiveLesson.Origin.GROUP_SCHEDULE)
        self.assertEqual(create_due_lessons(at(hour=17, minute=56)), 0)
        self.assertEqual(create_due_lessons(at(hour=18)), 0)

    def test_reschedule_and_cancel_reserve_original_occurrence(self):
        create_due_lessons(at(hour=17, minute=55))
        lesson = LiveLesson.objects.get()
        lesson.scheduled_at = at() + timedelta(days=1)
        lesson.save(update_fields=['scheduled_at', 'updated_at'])
        self.assertEqual(create_due_lessons(at(hour=17, minute=57)), 0)
        lesson.status = LiveLesson.Status.CANCELLED
        lesson.save(update_fields=['status'])
        self.assertEqual(create_due_lessons(at(hour=17, minute=58)), 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.lesson(timetable_slot=self.slot, timetable_date=at().date())

    def test_paused_group_and_inactive_teacher_do_not_generate(self):
        LearnGroup.objects.filter(pk=self.group.pk).update(is_studies=False)
        self.assertEqual(create_due_lessons(at(hour=17, minute=55)), 0)
        LearnGroup.objects.filter(pk=self.group.pk).update(is_studies=True)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertEqual(create_due_lessons(at(hour=17, minute=55)), 0)

    def test_weekday_multiple_groups_and_default_timezone(self):
        second = LearnGroup.objects.create(title='Другая', teacher=self.teacher, is_studies=True)
        Student.objects.create(user=get_user_model().objects.create_user(username='scheduler-student'),
                               contact='student', groups=second, is_learned=True)
        ClassesTimetable.objects.create(group=second, weekday='Среда', time_lesson=time(18))
        ClassesTimetable.objects.create(group=second, weekday='Четверг', time_lesson=time(18))
        from django.utils import timezone
        with timezone.override('America/New_York'):
            self.assertEqual(create_due_lessons(at(hour=17, minute=55).astimezone(ZoneInfo('UTC'))), 2)
        self.assertEqual(set(LiveLesson.objects.values_list('group_id', flat=True)), {self.group.pk, second.pk})

    def test_restart_catches_up_only_ongoing_slots_not_old_lessons(self):
        self.assertEqual(create_due_lessons(at(hour=18, minute=20)), 1)
        ClassesTimetable.objects.create(group=self.group, weekday='Среда', time_lesson=time(8))
        self.assertEqual(create_due_lessons(at(hour=20)), 0)
        self.assertEqual(LiveLesson.objects.count(), 1)

    def test_lesson_at_midnight_created_previous_day_and_survives_cutoff(self):
        ClassesTimetable.objects.create(group=self.group, weekday='Среда', time_lesson=time(0))
        self.assertEqual(create_due_lessons(at(day=29, hour=23, minute=54)), 0)
        self.assertEqual(create_due_lessons(at(day=29, hour=23, minute=55)), 1)
        lesson = LiveLesson.objects.get()
        self.assertEqual(lesson.scheduled_at, at(hour=0))
        self.assertEqual(end_expired_lessons(at(hour=0)), 0)
        self.assertEqual(create_due_lessons(at(hour=0)), 0)

    def test_midnight_closes_live_open_and_unused_scheduled_but_preserves_next_day(self):
        live = self.lesson(scheduled_at=at(day=29), status='live', started_at=at(day=29))
        open_lesson = self.lesson(group=None, audience='open', scheduled_at=at(day=29),
                                  status='live', started_at=at(day=29))
        waiting = self.lesson(scheduled_at=at(day=29))
        future = self.lesson()
        cancelled = self.lesson(scheduled_at=at(day=29), status='cancelled')
        self.assertEqual(end_expired_lessons(at(day=29, hour=23, minute=59)), 0)
        self.assertEqual(end_expired_lessons(at(hour=0)), 3)
        for lesson in (live, open_lesson, waiting):
            lesson.refresh_from_db()
            self.assertEqual(lesson.status, 'ended')
            self.assertEqual(lesson.ended_at, at(hour=0))
        self.assertTrue(live.room_cleanup_pending)
        self.assertFalse(waiting.room_cleanup_pending)
        future.refresh_from_db()
        cancelled.refresh_from_db()
        self.assertEqual(future.status, 'scheduled')
        self.assertEqual(cancelled.status, 'cancelled')
        self.assertEqual(end_expired_lessons(at(hour=0, second=10)), 0)

    def test_early_start_and_late_start_end_on_day_of_actual_start(self):
        early = self.lesson(status='live', started_at=at(day=29, hour=23))
        late = self.lesson(scheduled_at=at(day=29), status='live', started_at=at())
        self.assertEqual(end_expired_lessons(at(hour=0)), 1)
        early.refresh_from_db()
        late.refresh_from_db()
        self.assertEqual(early.status, 'ended')
        self.assertEqual(late.status, 'live')

    @patch('live_lessons.lifecycle.room_service')
    def test_delete_room_retries_and_removes_pending_flag_after_old_tokens_expire(self, service):
        lesson = self.lesson(status='ended', ended_at=at(hour=0), room_cleanup_pending=True)
        self.assertEqual(cleanup_closed_rooms(at(hour=0)), (1, 0))
        service.assert_called_with(lesson, 'DeleteRoom', {'room': lesson.room_name})
        lesson.refresh_from_db()
        self.assertTrue(lesson.room_cleanup_pending)
        service.side_effect = LiveKitAPIError('Не удалось связаться с медиасервером.')
        with self.assertLogs('live_lessons.lifecycle', level='WARNING'):
            self.assertEqual(cleanup_closed_rooms(at(hour=0, minute=6)), (0, 1))
        lesson.refresh_from_db()
        self.assertTrue(lesson.room_cleanup_pending)
        service.side_effect = LiveKitAPIError('Нет комнаты', status_code=404)
        self.assertEqual(cleanup_closed_rooms(at(hour=0, minute=7)), (1, 0))
        lesson.refresh_from_db()
        self.assertFalse(lesson.room_cleanup_pending)
        self.assertEqual(cleanup_closed_rooms(at(hour=0, minute=8)), (0, 0))

    @patch('live_lessons.lifecycle.room_service')
    def test_media_failure_does_not_undo_ending_or_creation(self, service):
        expired = self.lesson(status='live', scheduled_at=at(day=29), started_at=at(day=29))
        service.side_effect = LiveKitAPIError('Медиасервер недоступен')
        with self.assertLogs('live_lessons.lifecycle', level='WARNING'):
            result = sync_lessons(now=at(hour=17, minute=55))
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['ended'], 1)
        self.assertEqual(result['media_failures'], 1)
        expired.refresh_from_db()
        self.assertEqual(expired.status, 'ended')

    @patch('live_lessons.lifecycle.timezone.now')
    def test_command_once_and_interval_validation(self, now):
        now.return_value = at(hour=17, minute=55)
        output = StringIO()
        call_command('live_lesson_scheduler', once=True, stdout=output)
        self.assertIn("'created': 1", output.getvalue())
        call_command('live_lesson_scheduler', once=True, stdout=StringIO())
        self.assertEqual(LiveLesson.objects.count(), 1)
        with self.assertRaises(CommandError):
            call_command('live_lesson_scheduler', once=True, interval=0)

    def test_backfill_preserves_old_files_and_uses_original_date_after_move(self):
        first = self.lesson(timetable_slot=self.slot, scheduled_at=at() + timedelta(days=1))
        duplicate = self.lesson(timetable_slot=self.slot)
        LiveLessonReschedule.objects.create(lesson=first, old_scheduled_at=at(),
                                            new_scheduled_at=first.scheduled_at, changed_by=self.user)
        LiveLesson.objects.filter(pk__in=[first.pk, duplicate.pk]).update(timetable_date=None)
        migration = import_module('live_lessons.migrations.0006_lesson_automation')
        migration.remember_schedule_dates(apps, SimpleNamespace(connection=connection))
        first.refresh_from_db()
        duplicate.refresh_from_db()
        self.assertEqual(first.timetable_date, at().date())
        self.assertIsNone(duplicate.timetable_date)
        self.assertEqual(LiveLesson.objects.count(), 2)

    def test_manually_created_timetable_lesson_is_not_duplicated(self):
        lesson = self.lesson(timetable_slot=self.slot)
        self.assertEqual(lesson.timetable_date, at().date())
        self.assertEqual(create_due_lessons(at(hour=17, minute=55)), 0)

    def test_online_lessons_are_first_service_in_both_menus(self):
        for template in ('template/header.html', 'template/footer.html'):
            html = render_to_string(template, {'user': self.user})
            self.assertLess(html.index('Онлайн-занятия'), html.index('Твои'))

    @override_settings(DEBUG=True, LIVEKIT_URL='ws://127.0.0.1:7880',
                       LIVEKIT_API_KEY='test', LIVEKIT_API_SECRET='secret')
    @patch('live_lessons.views.timezone.now')
    def test_join_token_expires_at_midnight_and_no_new_access_after_cutoff(self, now):
        now.return_value = at(day=29, hour=23, minute=59)
        lesson = self.lesson(status='live', scheduled_at=at(day=29), started_at=at(day=29))
        self.client.force_login(self.user)
        url = reverse('live_lesson_join_token', args=[lesson.public_id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        claims = jwt.decode(response.json()['participant_token'], 'secret', algorithms=['HS256'],
                            options={'verify_exp': False, 'verify_nbf': False})
        self.assertEqual(claims['exp'], int(at(hour=0).timestamp()))
        self.assertLess(claims['nbf'], claims['exp'])
        self.assertNotIn('roomCreate', claims['video'])
        now.return_value = at(hour=0)
        self.assertEqual(self.client.post(url).status_code, 409)
        self.assertFalse(self.client.get(reverse('live_lesson_state', args=[lesson.public_id])).json()['can_join'])

    @patch('live_lessons.views.timezone.now')
    def test_start_cannot_reopen_yesterdays_waiting_lesson_before_scheduler_tick(self, now):
        now.return_value = at(hour=0)
        lesson = self.lesson(scheduled_at=at(day=29))
        self.client.force_login(self.user)
        response = self.client.post(reverse('live_lesson_change_status', args=[lesson.public_id, 'start']))
        self.assertEqual(response.status_code, 404)
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, 'scheduled')

    @override_settings(DEBUG=True, LIVEKIT_URL='ws://127.0.0.1:7880',
                       LIVEKIT_API_KEY='test', LIVEKIT_API_SECRET='secret')
    @patch('live_lessons.media.requests.post')
    def test_delete_room_has_server_only_room_create_grant(self, post):
        post.return_value.ok = True
        post.return_value.json.return_value = {}
        lesson = self.lesson()
        room_service(lesson, 'DeleteRoom', {'room': lesson.room_name})
        token = post.call_args.kwargs['headers']['Authorization'].removeprefix('Bearer ')
        self.assertEqual(jwt.decode(token, 'secret', algorithms=['HS256'])['video'], {'roomCreate': True})
