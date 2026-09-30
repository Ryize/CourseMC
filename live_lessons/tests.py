from io import BytesIO, StringIO
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

import jwt
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from Course.models import DirectionStudy, LearnGroup, Schedule, Student

from .guests import GUEST_ANIMALS
from .models import (LiveLesson, LiveLessonAttachment, LiveLessonChatArchive,
                     LiveLessonMessage, LiveLessonRemoval, LiveLessonReschedule)


class QualityLabTests(TestCase):
    def setUp(self):
        self.url = reverse('live_lesson_quality_lab')

    @override_settings(DEBUG=False)
    def test_unavailable_in_production(self):
        user = get_user_model().objects.create_user(username='lab-user', password='example-password')
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    @override_settings(DEBUG=True)
    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response['Location'])

    @override_settings(DEBUG=True)
    def test_authenticated_lab_is_no_cache_and_noindex(self):
        user = get_user_model().objects.create_user(username='lab-user', password='example-password')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Лаборатория качества связи')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertEqual(self.client.post(self.url).status_code, 405)

    @override_settings(DEBUG=False)
    def test_dev_tokens_forbidden_in_production(self):
        with self.assertRaises(CommandError):
            call_command('live_lesson_lab_tokens', stdout=StringIO())

    @override_settings(DEBUG=True)
    def test_dev_tokens_have_one_room_two_identities_and_short_expiry(self):
        output = StringIO()
        call_command('live_lesson_lab_tokens', stdout=output)
        token_lines = [line for line in output.getvalue().splitlines() if line.startswith('Участник ')]
        self.assertEqual(len(token_lines), 2)
        claims = [jwt.decode(line.split(': ', 1)[1], 'secret', algorithms=['HS256'], issuer='devkey')
                  for line in token_lines]
        self.assertEqual(claims[0]['video']['room'], claims[1]['video']['room'])
        self.assertNotEqual(claims[0]['sub'], claims[1]['sub'])
        for claim in claims:
            self.assertTrue(claim['video']['roomJoin'])
            self.assertTrue(claim['video']['canPublish'])
            self.assertTrue(claim['video']['canSubscribe'])
            self.assertEqual(claim['exp'] - claim['nbf'], 1800)


class LiveLessonFixture:
    def setUp(self):
        users = get_user_model()
        self.teacher_user = users.objects.create_user('lesson-teacher', password='password')
        self.teacher = Student.objects.create(
            user=self.teacher_user, groups_id=410, contact='teacher',
        )
        self.group = LearnGroup.objects.create(
            pk=410, title='Группа Python', teacher=self.teacher, is_studies=True,
        )
        self.student_user = users.objects.create_user('lesson-student', password='password')
        self.student = Student.objects.create(
            user=self.student_user, groups=self.group, contact='student', is_learned=True,
        )
        self.other_user = users.objects.create_user('other-student', password='password')
        self.other_profile = Student.objects.create(
            user=self.other_user, groups_id=411, contact='other', is_learned=True,
        )
        self.other_group = LearnGroup.objects.create(
            pk=411, title='Другая группа', teacher=self.other_profile, is_studies=True,
        )
        self.lesson = LiveLesson.objects.create(
            group=self.group, teacher=self.teacher, title='Практика Python',
            scheduled_at=timezone.now() + timedelta(days=1),
        )

    def detail_url(self, lesson=None):
        return reverse('live_lesson_detail', args=[(lesson or self.lesson).public_id])


class LiveLessonChatArchiveTests(LiveLessonFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.direction = DirectionStudy.objects.create(title='Python для архивов')
        self.schedule = Schedule.objects.create(direction=self.direction, theme='Функции', position=1)
        self.student.direction.add(self.direction)
        self.lesson.status = LiveLesson.Status.ENDED
        self.lesson.save(update_fields=('status',))
        self.save_url = reverse('live_lesson_save_chat_archive', args=[self.lesson.public_id])

    def save_archive(self):
        return self.client.post(self.save_url, {'target': f'{self.group.pk}:{self.schedule.pk}'})

    def test_teacher_saves_bundle_in_group_lesson_and_student_sees_chat_preview(self):
        LiveLessonMessage.objects.create(lesson=self.lesson, author=self.teacher_user,
                                         body='Команда:\npython manage.py migrate')
        self.client.force_login(self.teacher_user)
        with TemporaryDirectory() as private_dir, self.settings(PRIVATE_LIVE_LESSON_MEDIA_ROOT=private_dir):
            self.assertContains(self.client.get(self.detail_url()), 'Сохранить историю чата')
            self.assertEqual(self.save_archive().status_code, 302)
            archive = LiveLessonChatArchive.objects.get()
            self.assertEqual((archive.group, archive.schedule), (self.group, self.schedule))
            self.assertTrue(archive.file.name.endswith('.zip'))
            download_url = reverse('live_lesson_chat_archive_download', args=[archive.pk])
            preview_url = reverse('live_lesson_chat_archive_view', args=[archive.pk])
            self.assertContains(self.client.get(self.detail_url()), download_url)
            self.client.force_login(self.student_user)
            self.assertContains(self.client.get(reverse('schedule')), download_url)
            self.assertContains(self.client.get(reverse('schedule')), preview_url)
            self.assertNotContains(self.client.get(self.detail_url()), 'Сохранить историю чата')
            self.assertContains(self.client.get(preview_url), 'python manage.py migrate')
            inline = self.client.get(preview_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            self.assertContains(inline, 'lesson-chat-message-body')
            self.assertNotContains(inline, '<html')
            downloaded = self.client.get(download_url)
            self.assertEqual(downloaded.status_code, 200)
            with ZipFile(BytesIO(b''.join(downloaded.streaming_content))) as bundle:
                content = bundle.read('chat.txt').decode('utf-8')
            self.assertIn('Команда:\n  python manage.py migrate', content)
            self.assertIn('Группа: Группа Python', content)
            self.assertIn('no-store', downloaded['Cache-Control'])
            self.client.force_login(self.other_user)
            self.assertEqual(self.client.get(download_url).status_code, 404)
            self.assertEqual(self.client.get(preview_url).status_code, 404)
            self.assertNotContains(self.client.get(reverse('schedule')), download_url)
            self.client.logout()
            self.assertEqual(self.client.get(download_url).status_code, 302)

    def test_only_teacher_can_publish_and_target_must_belong_to_participating_group(self):
        LiveLessonMessage.objects.create(lesson=self.lesson, author=self.teacher_user, body='Пример')
        self.client.force_login(self.student_user)
        self.assertEqual(self.save_archive().status_code, 404)
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.post(self.save_url, {
            'target': f'{self.other_group.pk}:{self.schedule.pk}',
        }).status_code, 302)
        other_schedule = Schedule.objects.create(direction=DirectionStudy.objects.create(
            title='Нерелевантное направление'), theme='Чужой урок', position=1)
        self.assertEqual(self.client.post(self.save_url, {
            'target': f'{self.group.pk}:{other_schedule.pk}',
        }).status_code, 302)
        self.assertFalse(LiveLessonChatArchive.objects.exists())

    def test_additional_group_gets_its_own_archive_only(self):
        second_group = LearnGroup.objects.create(title='Вторая группа', teacher=self.teacher, is_studies=True)
        second_user = get_user_model().objects.create_user('second-archive-student')
        second_student = Student.objects.create(user=second_user, groups=second_group,
                                                contact='second', is_learned=True)
        second_student.direction.add(self.direction)
        self.lesson.additional_groups.add(second_group)
        LiveLessonMessage.objects.create(lesson=self.lesson, author=self.teacher_user, body='Для двух групп')
        self.client.force_login(self.teacher_user)
        with TemporaryDirectory() as private_dir, self.settings(PRIVATE_LIVE_LESSON_MEDIA_ROOT=private_dir):
            self.assertEqual(self.client.post(self.save_url, {
                'target': f'{second_group.pk}:{self.schedule.pk}',
            }).status_code, 302)
            archive = LiveLessonChatArchive.objects.get()
            download_url = reverse('live_lesson_chat_archive_download', args=[archive.pk])
            self.client.force_login(self.student_user)
            self.assertEqual(self.client.get(download_url).status_code, 404)
            self.assertNotContains(self.client.get(reverse('schedule')), download_url)
            self.client.force_login(second_user)
            self.assertEqual(self.client.get(download_url).status_code, 200)
            self.assertContains(self.client.get(reverse('schedule')), download_url)

    def test_attachment_link_is_private_and_snapshot_does_not_include_later_files(self):
        first = LiveLessonMessage.objects.create(lesson=self.lesson, author=self.teacher_user, body='Код')
        with TemporaryDirectory() as private_dir, self.settings(PRIVATE_LIVE_LESSON_MEDIA_ROOT=private_dir):
            attachment = LiveLessonAttachment.objects.create(
                message=first, file=SimpleUploadedFile('example.py', b'print(1)\n'),
                original_name='example.py', content_type='text/plain', size=9,
            )
            self.client.force_login(self.teacher_user)
            self.assertEqual(self.save_archive().status_code, 302)
            archive = LiveLessonChatArchive.objects.get()
            file_url = reverse('live_lesson_archive_attachment', args=[archive.pk, attachment.pk])
            archive_url = reverse('live_lesson_chat_archive_download', args=[archive.pk])
            with ZipFile(BytesIO(b''.join(self.client.get(archive_url).streaming_content))) as bundle:
                transcript = bundle.read('chat.txt').decode('utf-8')
                self.assertEqual(bundle.read(f'files/{first.pk:08d}-example.py'), b'print(1)\n')
            self.assertIn('example.py', transcript)
            self.assertIn(file_url, transcript)
            later = LiveLessonMessage.objects.create(lesson=self.lesson, author=self.teacher_user, body='Позже')
            later_attachment = LiveLessonAttachment.objects.create(
                message=later, file=SimpleUploadedFile('later.py', b'print(2)\n'),
                original_name='later.py', content_type='text/plain', size=9,
            )
            self.client.force_login(self.student_user)
            self.assertContains(self.client.get(reverse('live_lesson_chat_archive_view', args=[archive.pk])),
                                'example.py')
            attachment.file.delete(save=False)
            self.assertEqual(b''.join(self.client.get(file_url).streaming_content), b'print(1)\n')
            self.assertEqual(self.client.get(reverse('live_lesson_archive_attachment', args=[
                archive.pk, later_attachment.pk,
            ])).status_code, 404)
            self.client.force_login(self.other_user)
            self.assertEqual(self.client.get(file_url).status_code, 404)

    def test_existing_text_archive_is_upgraded_to_zip_without_losing_chat_or_files(self):
        message = LiveLessonMessage.objects.create(lesson=self.lesson, author=self.teacher_user, body='Старый чат')
        with TemporaryDirectory() as private_dir, self.settings(PRIVATE_LIVE_LESSON_MEDIA_ROOT=private_dir):
            LiveLessonAttachment.objects.create(
                message=message, file=SimpleUploadedFile('notes.txt', b'notes\n'),
                original_name='notes.txt', content_type='text/plain', size=6,
            )
            archive = LiveLessonChatArchive.objects.create(
                lesson=self.lesson, group=self.group, schedule=self.schedule,
                created_by=self.teacher_user, last_message_id=message.pk,
                file=SimpleUploadedFile('old.txt', b'Old saved chat\n'),
            )
            self.client.force_login(self.student_user)
            response = self.client.get(reverse('live_lesson_chat_archive_download', args=[archive.pk]))
            self.assertEqual(response.status_code, 200)
            with ZipFile(BytesIO(b''.join(response.streaming_content))) as bundle:
                self.assertEqual(bundle.read('chat.txt'), b'Old saved chat\n')
                self.assertEqual(bundle.read(f'files/{message.pk:08d}-notes.txt'), b'notes\n')
            archive.refresh_from_db()
            self.assertTrue(archive.file.name.endswith('.zip'))

    def test_empty_chat_duplicate_and_open_lesson_are_not_published(self):
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.save_archive().status_code, 302)
        self.assertFalse(LiveLessonChatArchive.objects.exists())
        LiveLessonMessage.objects.create(lesson=self.lesson, author=self.teacher_user, body='Одна версия')
        with TemporaryDirectory() as private_dir, self.settings(PRIVATE_LIVE_LESSON_MEDIA_ROOT=private_dir):
            self.assertEqual(self.save_archive().status_code, 302)
            self.assertEqual(self.save_archive().status_code, 302)
            self.assertEqual(LiveLessonChatArchive.objects.count(), 1)
        self.lesson.audience = LiveLesson.Audience.OPEN
        self.lesson.group = None
        self.lesson.save(update_fields=('audience', 'group'))
        self.assertEqual(self.save_archive().status_code, 404)

    def test_archive_write_requires_csrf_and_archived_program_lesson_is_hidden(self):
        LiveLessonMessage.objects.create(lesson=self.lesson, author=self.teacher_user, body='Текст')
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.teacher_user)
        self.assertEqual(strict_client.post(self.save_url, {
            'target': f'{self.group.pk}:{self.schedule.pk}',
        }).status_code, 403)
        with TemporaryDirectory() as private_dir, self.settings(PRIVATE_LIVE_LESSON_MEDIA_ROOT=private_dir):
            self.client.force_login(self.teacher_user)
            self.save_archive()
            archive = LiveLessonChatArchive.objects.get()
            self.schedule.is_archived = True
            self.schedule.save(update_fields=('is_archived',))
            self.client.force_login(self.student_user)
            self.assertEqual(self.client.get(reverse(
                'live_lesson_chat_archive_download', args=[archive.pk],
            )).status_code, 404)


class LiveLessonAccessTests(LiveLessonFixture, TestCase):

    def test_group_member_and_teacher_see_only_their_lessons(self):
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(self.detail_url()).status_code, 200)
        self.assertContains(self.client.get(reverse('live_lesson_list')), 'Практика Python')

        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(self.detail_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse('live_lesson_list')), 'Практика Python')

        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.get(self.detail_url()).status_code, 200)

    def test_anonymous_user_must_log_in(self):
        self.assertEqual(self.client.get(self.detail_url()).status_code, 302)

    def test_room_is_only_shown_during_active_lesson(self):
        self.client.force_login(self.student_user)
        self.assertNotContains(self.client.get(self.detail_url()), 'id="ll-room-join"')
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        response = self.client.get(self.detail_url())
        self.assertContains(response, 'id="ll-room-join"')
        self.assertContains(response, 'id="ll-room-copy-link"')
        self.assertContains(response, 'data-auto-copy="false"')
        self.assertNotContains(response, 'll-detail-grid')
        self.assertNotContains(response, 'll-room-live-badge')
        self.assertNotContains(response, 'Занятие в эфире')
        self.assertNotContains(response, 'Управление звонком')
        self.assertNotContains(response, 'll-link-field')
        self.assertContains(response, 'live_lessons/lesson_room.js')
        self.assertContains(response, reverse('live_lesson_join_token', args=[self.lesson.public_id]))
        self.assertContains(response, 'id="ll-room-fps"')
        self.assertContains(response, '<h1 id="ll-room-title">')
        self.assertNotContains(response, 'll-detail-head')
        self.assertContains(response, 'value="2k"')
        self.assertContains(response, 'value="1080"')
        self.assertContains(response, 'value="720"')
        self.assertContains(response, 'value="480"')
        self.assertContains(response, 'value="360"')
        self.assertContains(response, 'value="15"')
        self.assertContains(response, 'value="30"')
        self.assertContains(response, 'value="60"')
        self.assertContains(response, 'id="ll-room-chat-panel"')
        self.assertEqual(response.content.decode().count('id="ll-chat"'), 1)
        self.assertContains(response, 'id="ll-chat-feed"')
        self.assertContains(response, 'id="ll-chat-clear-file"')
        self.lesson.status = LiveLesson.Status.ENDED
        self.lesson.save(update_fields=('status',))
        self.assertNotContains(self.client.get(self.detail_url()), 'id="ll-room-join"')

    def test_teacher_gets_copy_button_for_lesson_link(self):
        self.client.force_login(self.teacher_user)
        scheduled = self.client.get(self.detail_url())
        self.assertContains(scheduled, 'data-auto-copy="true"')
        self.assertContains(scheduled, 'Скопировать ссылку')
        self.assertNotContains(scheduled, 'll-link-field')
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        live = self.client.get(self.detail_url())
        self.assertContains(live, 'id="ll-room-copy-link"')
        self.assertContains(live, 'data-auto-copy="true"')
        self.assertNotContains(live, 'll-detail-grid')

    def test_room_state_is_private_and_not_cached(self):
        url = reverse('live_lesson_state', args=[self.lesson.public_id])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.student_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'scheduled', 'can_join': False, 'removed': False})
        self.assertIn('no-store', response['Cache-Control'])
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        self.assertTrue(self.client.get(url).json()['can_join'])
        self.student.is_learned = False
        self.student.save(update_fields=('is_learned',))
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_teacher_can_create_extra_lesson_only_for_own_active_group(self):
        when = timezone.localtime(timezone.now() + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M')
        url = reverse('live_lesson_create')
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.post(url, {
            'group': self.group.pk, 'title': 'Новая встреча',
            'scheduled_at': when, 'duration_minutes': 60,
        }).status_code, 404)

        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.post(url, {
            'group': self.other_group.pk, 'title': 'Чужая встреча',
            'scheduled_at': when, 'duration_minutes': 60,
        }).status_code, 200)
        self.assertFalse(LiveLesson.objects.filter(title='Чужая встреча').exists())
        response = self.client.post(url, {
            'group': self.group.pk, 'title': 'Новая встреча',
            'scheduled_at': when, 'duration_minutes': 60,
        })
        self.assertEqual(response.status_code, 302)
        created = LiveLesson.objects.get(title='Новая встреча')
        self.assertEqual(created.teacher, self.teacher)
        self.assertEqual(created.origin, LiveLesson.Origin.EXTRA)

    def test_reschedule_records_original_and_new_time(self):
        new_time = timezone.localtime(timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        url = reverse('live_lesson_reschedule', args=[self.lesson.public_id])
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.post(url, {'scheduled_at': new_time}).status_code, 404)
        self.client.force_login(self.teacher_user)
        old_time = self.lesson.scheduled_at
        response = self.client.post(url, {'scheduled_at': new_time, 'reason': 'Перенос группы'})
        self.assertEqual(response.status_code, 302)
        self.lesson.refresh_from_db()
        record = LiveLessonReschedule.objects.get(lesson=self.lesson)
        self.assertEqual(record.old_scheduled_at, old_time)
        self.assertEqual(record.new_scheduled_at, self.lesson.scheduled_at)
        self.assertEqual(record.reason, 'Перенос группы')
        self.assertEqual(record.changed_by, self.teacher_user)

    def test_only_teacher_can_start_or_end_and_closed_lesson_cannot_be_moved(self):
        action_url = lambda action: reverse('live_lesson_change_status', args=[self.lesson.public_id, action])
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.post(action_url('start')).status_code, 404)
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.post(action_url('start')).status_code, 302)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, LiveLesson.Status.LIVE)
        self.assertIsNotNone(self.lesson.started_at)
        self.assertEqual(self.client.get(reverse('live_lesson_reschedule', args=[self.lesson.public_id])).status_code, 404)
        self.assertEqual(self.client.post(action_url('start')).status_code, 404)
        self.assertEqual(self.client.post(action_url('end')).status_code, 302)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, LiveLesson.Status.ENDED)
        self.assertIsNotNone(self.lesson.ended_at)

    def test_teacher_reassignment_revokes_old_teacher_access(self):
        self.group.teacher = self.other_profile
        self.group.save(update_fields=('teacher',))
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.get(self.detail_url()).status_code, 404)
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(self.detail_url()).status_code, 200)
        self.assertEqual(self.client.post(reverse(
            'live_lesson_change_status', args=[self.lesson.public_id, 'start'],
        )).status_code, 302)

    def test_inactive_group_cannot_start_lesson(self):
        self.student.is_learned = False
        self.student.save(update_fields=('is_learned',))
        self.assertFalse(LearnGroup.objects.get(pk=self.group.pk).is_studies)
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.post(reverse(
            'live_lesson_change_status', args=[self.lesson.public_id, 'start'],
        )).status_code, 404)

    def test_state_changes_require_csrf(self):
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.teacher_user)
        response = strict_client.post(reverse(
            'live_lesson_change_status', args=[self.lesson.public_id, 'start'],
        ))
        self.assertEqual(response.status_code, 403)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, LiveLesson.Status.SCHEDULED)

    def test_join_token_requires_csrf(self):
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.student_user)
        response = strict_client.post(reverse('live_lesson_join_token', args=[self.lesson.public_id]))
        self.assertEqual(response.status_code, 403)

    @override_settings(
        LIVEKIT_URL='wss://media.example.test', LIVEKIT_API_KEY='lesson-test-key',
        LIVEKIT_API_SECRET='strong-secret-for-testing-live-lesson-token',
    )
    def test_join_token_is_scoped_to_live_lesson_and_own_group(self):
        url = reverse('live_lesson_join_token', args=[self.lesson.public_id])
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 409)
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response.json()['server_url'], 'wss://media.example.test')
        claims = jwt.decode(
            response.json()['participant_token'],
            'strong-secret-for-testing-live-lesson-token',
            algorithms=['HS256'], issuer='lesson-test-key',
        )
        self.assertEqual(claims['sub'], f'course-user-{self.student_user.pk}')
        self.assertEqual(claims['video']['room'], self.lesson.room_name)
        self.assertTrue(claims['video']['roomJoin'])
        self.assertTrue(claims['video']['canPublishData'])
        self.assertEqual(claims['exp'] - claims['nbf'], 300)

        self.client.force_login(self.other_user)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.student_user)
        self.student.groups = self.other_group
        self.student.save(update_fields=('groups',))
        self.assertEqual(self.client.post(url).status_code, 404)

    @override_settings(LIVEKIT_URL='', LIVEKIT_API_KEY='', LIVEKIT_API_SECRET='')
    def test_join_token_fails_closed_without_media_configuration(self):
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('live_lesson_join_token', args=[self.lesson.public_id]))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('participant_token', response.json())

    @override_settings(
        DEBUG=False, LIVEKIT_URL='ws://127.0.0.1:7880',
        LIVEKIT_API_KEY='lesson-test-key',
        LIVEKIT_API_SECRET='strong-secret-for-testing-live-lesson-token',
    )
    def test_insecure_media_url_is_not_accepted_outside_debug(self):
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('live_lesson_join_token', args=[self.lesson.public_id]))
        self.assertEqual(response.status_code, 503)

    @patch('live_lessons.views.participant_in_room', return_value=True)
    def test_chat_requires_membership_and_live_lesson_for_sending(self, _in_room):
        messages_url = reverse('live_lesson_chat_messages', args=[self.lesson.public_id])
        send_url = reverse('live_lesson_chat_send', args=[self.lesson.public_id])
        self.assertEqual(self.client.get(messages_url).status_code, 302)
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(messages_url).status_code, 404)
        self.assertEqual(self.client.post(send_url, {'body': 'Чужой чат'}).status_code, 404)
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(messages_url).status_code, 409)
        self.assertEqual(self.client.post(send_url, {'body': 'Рано'}).status_code, 409)
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        response = self.client.post(send_url, {'body': '  Привет, группа!  '})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['message']['body'], 'Привет, группа!')
        self.assertEqual(LiveLessonMessage.objects.get().author, self.student_user)
        self.assertIn('no-store', self.client.get(messages_url)['Cache-Control'])
        self.lesson.status = LiveLesson.Status.ENDED
        self.lesson.save(update_fields=('status',))
        self.assertEqual(len(self.client.get(messages_url).json()['messages']), 1)
        self.assertEqual(self.client.post(send_url, {'body': 'Поздно'}).status_code, 409)
        self.student.is_learned = False
        self.student.save(update_fields=('is_learned',))
        self.assertEqual(self.client.get(messages_url).status_code, 404)

    @patch('live_lessons.views.participant_in_room', return_value=True)
    def test_chat_rejects_empty_oversized_and_invalid_cursor(self, _in_room):
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        self.client.force_login(self.student_user)
        send_url = reverse('live_lesson_chat_send', args=[self.lesson.public_id])
        messages_url = reverse('live_lesson_chat_messages', args=[self.lesson.public_id])
        self.assertEqual(self.client.post(send_url, {'body': '   '}).status_code, 400)
        self.assertEqual(self.client.post(send_url, {'body': 'x' * 3001}).status_code, 400)
        self.assertEqual(self.client.get(messages_url, {'before': '-1'}).status_code, 400)
        self.assertEqual(self.client.get(messages_url, {'after': '1', 'before': '2'}).status_code, 400)
        self.assertFalse(LiveLessonMessage.objects.exists())

    @patch('live_lessons.views.participant_in_room', return_value=True)
    def test_chat_paginates_its_history_without_leaking_other_lesson(self, _in_room):
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        other_lesson = LiveLesson.objects.create(
            group=self.other_group, teacher=self.other_profile, title='Другая комната',
            scheduled_at=timezone.now(), status=LiveLesson.Status.LIVE,
        )
        LiveLessonMessage.objects.create(lesson=other_lesson, author=self.other_user, body='Секрет')
        LiveLessonMessage.objects.bulk_create([
            LiveLessonMessage(lesson=self.lesson, author=self.teacher_user, body=f'Сообщение {index}')
            for index in range(55)
        ])
        url = reverse('live_lesson_chat_messages', args=[self.lesson.public_id])
        self.client.force_login(self.student_user)
        newest = self.client.get(url).json()
        self.assertEqual(len(newest['messages']), 50)
        self.assertTrue(newest['has_more'])
        self.assertEqual(newest['messages'][-1]['body'], 'Сообщение 54')
        older = self.client.get(url, {'before': newest['messages'][0]['id']}).json()
        self.assertEqual(len(older['messages']), 5)
        self.assertFalse(older['has_more'])
        self.assertEqual(older['messages'][0]['body'], 'Сообщение 0')
        self.assertNotIn('Секрет', str(newest) + str(older))

    @patch('live_lessons.views.participant_in_room', return_value=True)
    def test_private_attachment_is_validated_and_only_group_can_download(self, _in_room):
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        self.client.force_login(self.student_user)
        send_url = reverse('live_lesson_chat_send', args=[self.lesson.public_id])
        buffer = BytesIO()
        Image.new('RGB', (2, 2), (245, 120, 80)).save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        with TemporaryDirectory() as private_dir, self.settings(PRIVATE_LIVE_LESSON_MEDIA_ROOT=private_dir):
            bad = self.client.post(send_url, {'attachment': SimpleUploadedFile(
                'fake.png', b'not an image', content_type='image/png',
            )})
            self.assertEqual(bad.status_code, 400)
            self.assertFalse(LiveLessonMessage.objects.exists())
            uploaded = self.client.post(send_url, {'body': 'Схема', 'attachment': SimpleUploadedFile(
                'diagram.png', image_bytes, content_type='application/octet-stream',
            )})
            self.assertEqual(uploaded.status_code, 201)
            attachment = LiveLessonAttachment.objects.get()
            self.assertNotIn('diagram.png', attachment.file.name)
            self.assertEqual(attachment.content_type, 'image/png')
            download_url = reverse('live_lesson_chat_attachment', args=[self.lesson.public_id, attachment.pk])
            self.client.force_login(self.other_user)
            self.assertEqual(self.client.get(download_url).status_code, 404)
            self.client.force_login(self.student_user)
            downloaded = self.client.get(download_url)
            self.assertEqual(downloaded.status_code, 200)
            self.assertEqual(b''.join(downloaded.streaming_content), image_bytes)
            self.assertIn('attachment;', downloaded['Content-Disposition'])
            self.assertEqual(downloaded['X-Content-Type-Options'], 'nosniff')
            self.assertIn('no-store', downloaded['Cache-Control'])
            self.student.groups = self.other_group
            self.student.save(update_fields=('groups',))
            self.assertEqual(self.client.get(download_url).status_code, 404)

    @patch('live_lessons.views.participant_in_room', return_value=True)
    def test_python_attachment_with_cyrillic_at_validation_boundary(self, _in_room):
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        self.client.force_login(self.student_user)
        send_url = reverse('live_lesson_chat_send', args=[self.lesson.public_id])
        source = b'#' * 511 + 'Я'.encode('utf-8') + b'\nprint("ok")\n'
        with TemporaryDirectory() as private_dir, self.settings(PRIVATE_LIVE_LESSON_MEDIA_ROOT=private_dir):
            response = self.client.post(send_url, {'body': 'Код', 'attachment': SimpleUploadedFile(
                'example.py', source, content_type='text/x-python',
            )})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(LiveLessonAttachment.objects.get().content_type, 'text/plain')
            invalid = self.client.post(send_url, {'attachment': SimpleUploadedFile(
                'not-text.py', b'print(1)\n' + b'a' * 600 + b'\x00', content_type='text/x-python',
            )})
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(LiveLessonMessage.objects.count(), 1)

    def test_chat_send_requires_csrf(self):
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.student_user)
        response = strict_client.post(reverse('live_lesson_chat_send', args=[self.lesson.public_id]),
                                      {'body': 'Без CSRF'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(LiveLessonMessage.objects.exists())


class LiveLessonRoomControlTests(LiveLessonFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        self.moderate_url = reverse('live_lesson_moderate', args=[self.lesson.public_id])

    @patch('live_lessons.views.participant_in_room', return_value=False)
    def test_chat_requires_actual_room_membership(self, _in_room):
        self.client.force_login(self.student_user)
        messages_url = reverse('live_lesson_chat_messages', args=[self.lesson.public_id])
        send_url = reverse('live_lesson_chat_send', args=[self.lesson.public_id])
        self.assertEqual(self.client.get(messages_url).status_code, 409)
        self.assertEqual(self.client.post(send_url, {'body': 'До входа'}).status_code, 409)
        self.assertFalse(LiveLessonMessage.objects.exists())

    @patch('live_lessons.views.participant_in_room', return_value=False)
    def test_live_attachment_requires_room_membership(self, _in_room):
        self.client.force_login(self.student_user)
        message = LiveLessonMessage.objects.create(
            lesson=self.lesson, author=self.teacher_user, body='Файл',
        )
        attachment = LiveLessonAttachment.objects.create(
            message=message, original_name='note.txt', content_type='text/plain', size=4,
        )
        url = reverse('live_lesson_chat_attachment', args=[self.lesson.public_id, attachment.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        _in_room.assert_called_once()

    def test_only_teacher_can_moderate_and_cannot_target_self(self):
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.post(self.moderate_url, {
            'action': 'remove', 'identity': f'course-user-{self.teacher_user.pk}',
        }).status_code, 404)
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.post(self.moderate_url, {
            'action': 'remove', 'identity': f'course-user-{self.teacher_user.pk}',
        }).status_code, 403)
        self.assertEqual(self.client.post(self.moderate_url, {
            'action': 'remove', 'identity': '../another-room',
        }).status_code, 400)

    @patch('live_lessons.views.room_service')
    @override_settings(
        LIVEKIT_URL='wss://media.example.test', LIVEKIT_API_KEY='lesson-test-key',
        LIVEKIT_API_SECRET='strong-secret-for-testing-live-lesson-token',
    )
    def test_mute_and_remove_participant(self, service):
        service.return_value = {'tracks': [{'sid': 'TR_mic', 'source': 'MICROPHONE', 'muted': False}]}
        self.client.force_login(self.teacher_user)
        identity = f'course-user-{self.student_user.pk}'
        self.assertEqual(self.client.post(self.moderate_url, {
            'action': 'mute', 'identity': identity,
        }).status_code, 200)
        service.assert_any_call(self.lesson, 'MutePublishedTrack', {
            'room': self.lesson.room_name, 'identity': identity, 'track_sid': 'TR_mic', 'muted': True,
        })
        self.assertEqual(self.client.post(self.moderate_url, {
            'action': 'remove', 'identity': identity,
        }).status_code, 200)
        service.assert_any_call(self.lesson, 'RemoveParticipant', {
            'room': self.lesson.room_name, 'identity': identity,
        })
        self.assertTrue(LiveLessonRemoval.objects.filter(lesson=self.lesson, identity=identity).exists())
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.post(reverse('live_lesson_join_token', args=[self.lesson.public_id])).status_code, 403)
        self.assertEqual(self.client.get(reverse('live_lesson_state', args=[self.lesson.public_id])).json()['removed'], True)
        self.assertEqual(self.client.post(reverse('live_lesson_chat_send', args=[self.lesson.public_id]), {
            'body': 'Я вернулся',
        }).status_code, 403)

    @patch('live_lessons.media.requests.post')
    @override_settings(
        LIVEKIT_URL='wss://coursemc.ru/livekit', LIVEKIT_API_URL='http://livekit:7880',
        LIVEKIT_API_KEY='lesson-test-key', LIVEKIT_API_SECRET='strong-secret-for-testing-live-lesson-token',
    )
    def test_room_admin_request_uses_internal_url_and_scoped_token(self, post):
        from .media import room_service
        post.return_value.ok = True
        post.return_value.json.return_value = {'identity': 'course-user-1'}
        room_service(self.lesson, 'GetParticipant', {
            'room': self.lesson.room_name, 'identity': 'course-user-1',
        })
        self.assertEqual(post.call_args.args[0], 'http://livekit:7880/twirp/livekit.RoomService/GetParticipant')
        token = post.call_args.kwargs['headers']['Authorization'].removeprefix('Bearer ')
        claims = jwt.decode(token, 'strong-secret-for-testing-live-lesson-token',
                            algorithms=['HS256'], issuer='lesson-test-key')
        self.assertEqual(claims['video'], {'roomAdmin': True, 'room': self.lesson.room_name})


class LiveLessonAudienceTests(LiveLessonFixture, TestCase):
    """Те же участники позволяют проверить новое правило доступа без обходных фикстур."""

    def test_another_selected_group_shares_room_but_unselected_group_does_not(self):
        second_group = LearnGroup.objects.create(
            title='Группа Django', teacher=self.teacher, is_studies=True,
        )
        second_user = get_user_model().objects.create_user('second-student', password='password')
        Student.objects.create(user=second_user, groups=second_group, contact='second', is_learned=True)
        when = timezone.localtime(timezone.now() + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M')
        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('live_lesson_create'), {
            'audience': 'groups', 'group': self.group.pk,
            'additional_groups': [second_group.pk], 'title': 'Общий разбор',
            'scheduled_at': when, 'duration_minutes': 60,
        })
        self.assertEqual(response.status_code, 302)
        lesson = LiveLesson.objects.get(title='Общий разбор')
        self.assertEqual(list(lesson.additional_groups.all()), [second_group])

        self.client.force_login(second_user)
        self.assertContains(self.client.get(reverse('live_lesson_list')), 'Общий разбор')
        self.assertContains(self.client.get(self.detail_url(lesson)), 'Группа Django')
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(self.detail_url(lesson)).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.detail_url(lesson)).status_code, 302)

        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.post(reverse(
            'live_lesson_change_status', args=[lesson.public_id, 'start'],
        )).status_code, 302)
        self.client.force_login(second_user)
        self.assertTrue(self.client.get(reverse('live_lesson_state', args=[lesson.public_id])).json()['can_join'])
        Student.objects.filter(user=second_user).update(is_learned=False)
        self.assertEqual(self.client.get(self.detail_url(lesson)).status_code, 404)

    def test_extra_group_must_belong_to_teacher_and_not_duplicate_primary(self):
        when = timezone.localtime(timezone.now() + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M')
        url = reverse('live_lesson_create')
        self.client.force_login(self.teacher_user)
        for extra_group in (self.other_group, self.group):
            response = self.client.post(url, {
                'audience': 'groups', 'group': self.group.pk,
                'additional_groups': [extra_group.pk], 'title': 'Недопустимая группа',
                'scheduled_at': when, 'duration_minutes': 60,
            })
            self.assertEqual(response.status_code, 200)
        self.assertFalse(LiveLesson.objects.filter(title='Недопустимая группа').exists())

    @override_settings(
        LIVEKIT_URL='wss://media.example.test', LIVEKIT_API_KEY='lesson-test-key',
        LIVEKIT_API_SECRET='strong-secret-for-testing-live-lesson-token',
    )
    @patch('live_lessons.views.participant_in_room', return_value=True)
    def test_open_lesson_guest_uses_stable_animal_name_and_can_chat(self, _in_room):
        when = timezone.localtime(timezone.now() + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M')
        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('live_lesson_create'), {
            'audience': 'open', 'title': 'Открытая лекция',
            'scheduled_at': when, 'duration_minutes': 60,
        })
        self.assertEqual(response.status_code, 302)
        lesson = LiveLesson.objects.get(title='Открытая лекция')
        self.assertIsNone(lesson.group)
        self.assertEqual(lesson.audience, LiveLesson.Audience.OPEN)
        detail_url = self.detail_url(lesson)
        token_url = reverse('live_lesson_join_token', args=[lesson.public_id])
        state_url = reverse('live_lesson_state', args=[lesson.public_id])
        messages_url = reverse('live_lesson_chat_messages', args=[lesson.public_id])
        send_url = reverse('live_lesson_chat_send', args=[lesson.public_id])

        guest_client = Client()
        scheduled = guest_client.get(detail_url)
        self.assertEqual(scheduled.status_code, 200)
        self.assertContains(scheduled, 'Открытый урок')
        self.assertEqual(guest_client.post(token_url).status_code, 409)
        self.assertEqual(guest_client.get(messages_url).status_code, 409)

        self.assertEqual(self.client.post(reverse(
            'live_lesson_change_status', args=[lesson.public_id, 'start'],
        )).status_code, 302)
        live_page = guest_client.get(detail_url)
        self.assertContains(live_page, 'id="ll-room-join"')
        self.assertContains(live_page, 'id="ll-chat-form"')
        self.assertContains(live_page, 'data-auto-copy="false"')
        self.assertTrue(guest_client.get(state_url).json()['can_join'])
        first_token = guest_client.post(token_url)
        self.assertEqual(first_token.status_code, 200)
        self.assertIn('no-store', first_token['Cache-Control'])
        claims = jwt.decode(
            first_token.json()['participant_token'],
            'strong-secret-for-testing-live-lesson-token',
            algorithms=['HS256'], issuer='lesson-test-key',
        )
        self.assertIn(claims['name'], GUEST_ANIMALS)
        self.assertTrue(claims['sub'].startswith('lesson-guest-'))
        self.assertIn(claims['name'], live_page.content.decode())
        self.assertIn(f"guest:{claims['sub'].removeprefix('lesson-guest-')}", live_page.content.decode())
        repeated = jwt.decode(
            guest_client.post(token_url).json()['participant_token'],
            'strong-secret-for-testing-live-lesson-token',
            algorithms=['HS256'], issuer='lesson-test-key',
        )
        self.assertEqual((claims['sub'], claims['name']), (repeated['sub'], repeated['name']))
        self.assertIn(claims['name'], guest_client.get(detail_url).content.decode())
        other_guest = jwt.decode(
            Client().post(token_url).json()['participant_token'],
            'strong-secret-for-testing-live-lesson-token',
            algorithms=['HS256'], issuer='lesson-test-key',
        )
        self.assertNotEqual(other_guest['sub'], claims['sub'])
        logged_in_outsider = Client()
        logged_in_outsider.force_login(self.other_user)
        self.assertEqual(logged_in_outsider.get(detail_url).status_code, 200)
        self.assertEqual(logged_in_outsider.post(token_url).status_code, 200)

        sent = guest_client.post(send_url, {'body': 'Привет от гостя'})
        self.assertEqual(sent.status_code, 201)
        self.assertEqual(sent.json()['message']['author'], claims['name'])
        self.assertIsNone(LiveLessonMessage.objects.get().author)
        self.assertEqual(guest_client.get(messages_url).json()['messages'][0]['body'], 'Привет от гостя')
        with TemporaryDirectory() as private_dir, self.settings(PRIVATE_LIVE_LESSON_MEDIA_ROOT=private_dir):
            uploaded = guest_client.post(send_url, {'attachment': SimpleUploadedFile(
                'notes.txt', b'lesson notes', content_type='text/plain',
            )})
            self.assertEqual(uploaded.status_code, 201)
            download_url = uploaded.json()['message']['attachment']['url']
            downloaded = Client().get(download_url)
            self.assertEqual(downloaded.status_code, 200)
            self.assertEqual(b''.join(downloaded.streaming_content), b'lesson notes')

        self.assertEqual(guest_client.post(reverse(
            'live_lesson_change_status', args=[lesson.public_id, 'end'],
        )).status_code, 302)
        self.assertEqual(self.client.post(reverse(
            'live_lesson_change_status', args=[lesson.public_id, 'end'],
        )).status_code, 302)
        self.assertFalse(guest_client.get(state_url).json()['can_join'])
        self.assertEqual(guest_client.post(token_url).status_code, 409)
        self.assertEqual(guest_client.post(send_url, {'body': 'Поздно'}).status_code, 409)
        self.assertEqual(len(guest_client.get(messages_url).json()['messages']), 2)

    @override_settings(
        LIVEKIT_URL='wss://media.example.test', LIVEKIT_API_KEY='lesson-test-key',
        LIVEKIT_API_SECRET='strong-secret-for-testing-live-lesson-token',
    )
    @patch('live_lessons.views.participant_in_room', return_value=True)
    def test_open_guest_chat_and_token_require_csrf(self, _in_room):
        lesson = LiveLesson.objects.create(
            teacher=self.teacher, title='Открытый урок', audience=LiveLesson.Audience.OPEN,
            scheduled_at=timezone.now(), status=LiveLesson.Status.LIVE,
        )
        client = Client(enforce_csrf_checks=True)
        client.get(self.detail_url(lesson))
        self.assertEqual(client.post(reverse('live_lesson_join_token', args=[lesson.public_id])).status_code, 403)
        self.assertEqual(client.post(reverse(
            'live_lesson_chat_send', args=[lesson.public_id],
        ), {'body': 'Без CSRF'}).status_code, 403)
        self.assertFalse(LiveLessonMessage.objects.exists())
        csrf = client.cookies['csrftoken'].value
        self.assertEqual(client.post(
            reverse('live_lesson_join_token', args=[lesson.public_id]),
            HTTP_X_CSRFTOKEN=csrf,
        ).status_code, 200)
        self.assertEqual(client.post(
            reverse('live_lesson_chat_send', args=[lesson.public_id]),
            {'body': 'С CSRF'}, HTTP_X_CSRFTOKEN=csrf,
        ).status_code, 201)

    @patch('live_lessons.views.participant_in_room', return_value=True)
    def test_open_guest_message_rate_limit(self, _in_room):
        lesson = LiveLesson.objects.create(
            teacher=self.teacher, title='Открытый урок', audience=LiveLesson.Audience.OPEN,
            scheduled_at=timezone.now(), status=LiveLesson.Status.LIVE,
        )
        client = Client()
        client.get(self.detail_url(lesson))
        guest = client.session[f'live_lesson_guest_{lesson.public_id.hex}']
        LiveLessonMessage.objects.bulk_create([
            LiveLessonMessage(lesson=lesson, guest_id=guest['id'], guest_name=guest['name'], body='Сообщение')
            for _ in range(20)
        ])
        response = client.post(reverse('live_lesson_chat_send', args=[lesson.public_id]), {'body': 'Ещё'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(LiveLessonMessage.objects.filter(lesson=lesson).count(), 20)

    def test_anonymous_guest_cannot_use_private_lesson_endpoints(self):
        self.lesson.status = LiveLesson.Status.LIVE
        self.lesson.save(update_fields=('status',))
        for name, method in (
            ('live_lesson_detail', 'get'), ('live_lesson_state', 'get'),
            ('live_lesson_join_token', 'post'), ('live_lesson_chat_messages', 'get'),
            ('live_lesson_chat_send', 'post'),
        ):
            response = getattr(self.client, method)(reverse(name, args=[self.lesson.public_id]))
            self.assertEqual(response.status_code, 302, name)

    def test_guest_animal_pool_has_thirty_distinct_normal_names(self):
        self.assertEqual(len(GUEST_ANIMALS), 30)
        self.assertEqual(len(set(GUEST_ANIMALS)), 30)

    def test_teacher_can_create_open_lesson_without_active_group(self):
        self.student.is_learned = False
        self.student.save(update_fields=('is_learned',))
        self.assertFalse(LearnGroup.objects.get(pk=self.group.pk).is_studies)
        self.client.force_login(self.teacher_user)
        when = timezone.localtime(timezone.now() + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M')
        response = self.client.post(reverse('live_lesson_create'), {
            'audience': 'open', 'title': 'Открытая консультация',
            'scheduled_at': when, 'duration_minutes': 60,
        })
        self.assertEqual(response.status_code, 302)
        lesson = LiveLesson.objects.get(title='Открытая консультация')
        self.assertIsNone(lesson.group)
        self.assertEqual(self.client.post(reverse(
            'live_lesson_change_status', args=[lesson.public_id, 'start'],
        )).status_code, 302)
