"""Небольшой идемпотентный планировщик: один процесс, без Celery/Redis."""

import logging
from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from Course.models import ClassesTimetable

from .media import LiveKitAPIError, room_service
from .models import LiveLesson

logger = logging.getLogger(__name__)
WEEKDAYS = ('Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье')
LEAD_TIME = timedelta(minutes=5)
TOKEN_LIFETIME = timedelta(minutes=5)


def create_due_lessons(now):
    school_timezone = timezone.get_default_timezone()
    local_now = timezone.localtime(now, school_timezone)
    horizon = timezone.localtime(now + LEAD_TIME, school_timezone)
    days = {local_now.date(), horizon.date()}
    created = 0
    slots = ClassesTimetable.objects.filter(
        group__is_studies=True, group__teacher__user__is_active=True,
        weekday__in=[WEEKDAYS[day.weekday()] for day in days],
    ).select_related('group')
    for slot in slots:
        seconds = slot.duration.hour * 3600 + slot.duration.minute * 60 + slot.duration.second
        minutes = max(15, min(240, (seconds + 59) // 60))
        for day in sorted(days):
            if slot.weekday != WEEKDAYS[day.weekday()]:
                continue
            start = timezone.make_aware(datetime.combine(day, slot.time_lesson), school_timezone)
            # При рестарте догоняем только ещё актуальные занятия, не создаём прошедшие недели.
            if start > now + LEAD_TIME or start + timedelta(seconds=seconds) <= now:
                continue
            _, was_created = LiveLesson.objects.get_or_create(
                timetable_slot=slot, timetable_date=day,
                defaults={
                    'group': slot.group, 'teacher_id': slot.group.teacher_id,
                    'title': 'Урок', 'scheduled_at': start, 'duration_minutes': minutes,
                    'origin': LiveLesson.Origin.GROUP_SCHEDULE,
                },
            )
            created += int(was_created)
    return created


def end_expired_lessons(now):
    school_timezone = timezone.get_default_timezone()
    day = timezone.localtime(now, school_timezone).date()
    midnight = timezone.make_aware(datetime.combine(day, time.min), school_timezone)
    expired = LiveLesson.objects.filter(
        Q(status=LiveLesson.Status.SCHEDULED, scheduled_at__lt=midnight) |
        Q(status=LiveLesson.Status.LIVE, started_at__lt=midnight) |
        Q(status=LiveLesson.Status.LIVE, started_at__isnull=True, scheduled_at__lt=midnight),
    )
    ended = 0
    for lesson in expired.iterator():
        # Условное обновление не затирает одновременный перенос/начало преподавателем.
        ended += LiveLesson.objects.filter(
            pk=lesson.pk, status=lesson.status, updated_at=lesson.updated_at,
        ).update(
            status=LiveLesson.Status.ENDED, ended_at=lesson.auto_end_at,
            updated_at=now, room_cleanup_pending=lesson.status == LiveLesson.Status.LIVE,
        )
    return ended


def cleanup_closed_rooms(now):
    closed = failures = 0
    for lesson in LiveLesson.objects.filter(
        status=LiveLesson.Status.ENDED, room_cleanup_pending=True,
    ).order_by('ended_at', 'pk')[:50]:
        try:
            room_service(lesson, 'DeleteRoom', {'room': lesson.room_name})
        except LiveKitAPIError as error:
            if error.status_code != 404:
                failures += 1
                logger.warning('Не удалось закрыть медиакомнату урока %s: %s', lesson.pk, error)
                # Недоступный медиасервер не должен задерживать планирование других уроков.
                break
        closed += 1
        # Повторяем закрытие до истечения ранее выданных токенов self-hosted LiveKit.
        if lesson.ended_at and now >= lesson.ended_at + TOKEN_LIFETIME:
            LiveLesson.objects.filter(pk=lesson.pk, status=LiveLesson.Status.ENDED).update(
                room_cleanup_pending=False,
            )
    return closed, failures


def sync_lessons(*, now=None):
    from .classroom import retry_media_policies
    now = now or timezone.now()
    ended = end_expired_lessons(now)
    created = create_due_lessons(now)
    closed, failures = cleanup_closed_rooms(now)
    failures += retry_media_policies(now)
    return {'created': created, 'ended': ended, 'rooms_checked': closed, 'media_failures': failures}
