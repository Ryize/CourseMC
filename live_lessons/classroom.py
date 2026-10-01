"""Допуск в комнату и серверные права публикации потоков."""

import base64
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .guests import guest_for_lesson
from .media import LiveKitAPIError, participant_identity, room_service
from .models import LiveLesson, LiveLessonParticipant

PRESENCE_TTL = timedelta(seconds=45)
logger = logging.getLogger(__name__)


def host_identities(lesson):
    identities = {f'course-user-{lesson.teacher.user_id}'}
    if lesson.group_id:
        identities.add(f'course-user-{lesson.group.teacher.user_id}')
    return sorted(identities)


def notify_waiting_request(lesson):
    """Сигнал через соединение звонка, а не замедляемый фоновый таймер вкладки."""
    try:
        room_service(lesson, 'SendData', {
            'room': lesson.room_name,
            'data': base64.b64encode(b'refresh').decode('ascii'),
            'kind': 'RELIABLE', 'topic': 'lesson-waiting-updated',
            'destination_identities': host_identities(lesson),
        })
    except LiveKitAPIError as error:
        # Если преподаватель ещё не подключился, он увидит очередь при входе/опросе.
        # Сбой уведомления не должен лишать ученика заявки на вход.
        if error.status_code != 404:
            logger.warning('Waiting room notification unavailable: %s', error)


def display_name(request, lesson):
    if request.user.is_authenticated:
        return (request.user.get_full_name().strip() or request.user.username)[:160]
    return guest_for_lesson(request, lesson)['name']


def admission_for_join(request, lesson):
    from .views import lesson_is_teacher
    identity = participant_identity(request, lesson)
    participant = lesson.participants.filter(identity=identity).first()
    teacher = lesson_is_teacher(request, lesson)
    if participant and participant.admission == 'denied' and not teacher:
        return 'denied'
    if lesson.entry_locked and not teacher and (not participant or participant.admission != 'admitted'):
        return 'locked'
    now = timezone.now()
    fresh_wait = False
    if not participant:
        participant, created = LiveLessonParticipant.objects.get_or_create(
            lesson=lesson, identity=identity,
            defaults={'name': display_name(request, lesson), 'requested_at': now,
                      'admission': 'waiting' if lesson.waiting_room_enabled and not teacher else 'admitted'},
        )
        fresh_wait = created and participant.admission == 'waiting'
    if teacher or not lesson.waiting_room_enabled:
        participant.admission = 'admitted'
    elif participant.admission == 'left':
        participant.admission = 'waiting'
        participant.requested_at = now
        fresh_wait = True
    participant.name = display_name(request, lesson)
    participant.last_seen_at = now
    participant.save(update_fields=['admission', 'requested_at', 'name', 'last_seen_at'])
    if fresh_wait:
        transaction.on_commit(lambda: notify_waiting_request(lesson))
    return participant.admission


def publish_sources(lesson, *, teacher=False):
    sources = ['camera']
    if teacher or lesson.students_can_unmute:
        sources.append('microphone')
    if teacher or lesson.students_can_share_screen:
        sources.extend(['screen_share', 'screen_share_audio'])
    return sources


def sync_media_policy(lesson, *, now=None):
    """Повторяем применение правил до истечения старых Self-Hosted токенов."""
    now = now or timezone.now()
    try:
        participants = room_service(lesson, 'ListParticipants', {'room': lesson.room_name}).get('participants', [])
    except LiveKitAPIError as error:
        if error.status_code != 404:
            raise
        participants = []
    host_ids = set(host_identities(lesson))
    api_sources = {'camera': 'CAMERA', 'microphone': 'MICROPHONE',
                   'screen_share': 'SCREEN_SHARE', 'screen_share_audio': 'SCREEN_SHARE_AUDIO'}
    muted = 0
    for person in participants:
        identity = person.get('identity')
        if not identity or identity in host_ids:
            continue
        if lesson.policy_sync_until:
            try:
                room_service(lesson, 'UpdateParticipant', {
                    'room': lesson.room_name, 'identity': identity,
                    'permission': {'can_publish': True, 'can_subscribe': True, 'can_publish_data': True,
                                   'can_publish_sources': [api_sources[source] for source in publish_sources(lesson)]},
                })
            except LiveKitAPIError as error:
                if error.status_code == 404:  # Участник вышел между List и Update.
                    continue
                raise
        for track in person.get('tracks', []):
            source = track.get('source')
            forbidden_mic = source in ('MICROPHONE', 2) and (lesson.mute_all_pending or not lesson.students_can_unmute)
            forbidden_screen = source in ('SCREEN_SHARE', 'SCREEN_SHARE_AUDIO', 3, 4) and not lesson.students_can_share_screen
            if (forbidden_mic or forbidden_screen) and track.get('sid') and not track.get('muted'):
                try:
                    room_service(lesson, 'MutePublishedTrack', {
                        'room': lesson.room_name, 'identity': identity, 'track_sid': track['sid'], 'muted': True,
                    })
                    muted += 1
                except LiveKitAPIError as error:
                    if error.status_code != 404:  # Отменённый/отозванный трек уже исчез.
                        raise
    if lesson.mute_all_pending:
        LiveLesson.objects.filter(pk=lesson.pk, updated_at=lesson.updated_at).update(mute_all_pending=False)
    if lesson.policy_sync_until and now >= lesson.policy_sync_until:
        LiveLesson.objects.filter(pk=lesson.pk, policy_sync_until=lesson.policy_sync_until).update(policy_sync_until=None)
    return muted


def retry_media_policies(now):
    failures = 0
    for lesson in LiveLesson.objects.filter(status='live').filter(
        Q(policy_sync_until__isnull=False) | Q(mute_all_pending=True),
    ).select_related('teacher', 'group__teacher'):
        try:
            sync_media_policy(lesson, now=now)
        except LiveKitAPIError:
            failures += 1
            break
    return failures


def may_read_chat(request, lesson):
    """После урока открытая ссылка не обходит решение преподавателя о допуске."""
    from .views import lesson_is_teacher
    identity = participant_identity(request, lesson)
    if lesson.removed_participants.filter(identity=identity).exists():
        return False
    if lesson_is_teacher(request, lesson):
        return True
    if lesson.audience != LiveLesson.Audience.OPEN:
        return True  # Для закрытых групп доступ уже проверен lesson_for_request.
    if not lesson.waiting_room_enabled and not lesson.entry_locked:
        return not lesson.participants.filter(identity=identity, admission='denied').exists()
    return lesson.participants.filter(identity=identity, admission='admitted').exists()
