from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .classroom import PRESENCE_TTL, sync_media_policy
from .media import LiveKitAPIError, participant_identity, participant_in_room
from .models import LiveLessonParticipant, LiveLessonRemoval
from .views import lesson_for_request, lesson_is_teacher, room_available, teacher_lesson_or_404


@require_GET
@never_cache
def classroom_state(request, public_id):
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        return redirect_to_login(request.get_full_path())
    now = timezone.now()
    identity = participant_identity(request, lesson)
    own = lesson.participants.filter(identity=identity).first()
    if own and (own.admission == 'waiting' or (
        own.hand_raised_at and request.GET.get('presence') == 'connected'
    )) and own.last_seen_at < now - timedelta(seconds=15):
        lesson.participants.filter(pk=own.pk).update(last_seen_at=now)
        own.last_seen_at = now
    teacher = lesson_is_teacher(request, lesson)
    active = room_available(lesson)
    removed = LiveLessonRemoval.objects.filter(lesson=lesson, identity=identity).exists()
    waiting = lesson.participants.filter(admission='waiting', last_seen_at__gte=now - PRESENCE_TTL).order_by('requested_at', 'pk')
    hands = lesson.participants.filter(admission='admitted', hand_raised_at__isnull=False,
                                      last_seen_at__gte=now - PRESENCE_TTL).order_by('hand_raised_at', 'pk')
    return JsonResponse({
        'active': active, 'teacher': teacher,
        'settings': {'waiting_room': lesson.waiting_room_enabled, 'entry_locked': lesson.entry_locked,
                     'microphone': lesson.students_can_unmute, 'screen': lesson.students_can_share_screen},
        'own': {'identity': identity, 'admission': 'denied' if removed else own.admission if own else None,
                'hand_raised': bool(own and own.hand_raised_at),
                'entry_allowed': teacher or not lesson.entry_locked or bool(own and own.admission == 'admitted')},
        'waiting': [{'identity': item.identity, 'name': item.name, 'request': item.requested_at.isoformat()}
                    for item in waiting[:50]] if teacher and active else [],
        'hands': [{'identity': item.identity, 'name': item.name} for item in hands[:100]]
                 if active and not removed and (teacher or own and own.admission == 'admitted') else [],
        'sync_pending': bool(lesson.policy_sync_until or lesson.mute_all_pending) if teacher else False,
    })


@require_POST
@never_cache
def classroom_action(request, public_id):
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        return redirect_to_login(request.get_full_path())
    if not room_available(lesson):
        return JsonResponse({'error': 'Занятие сейчас недоступно.'}, status=409)
    identity = participant_identity(request, lesson)
    if LiveLessonRemoval.objects.filter(lesson=lesson, identity=identity).exists():
        return JsonResponse({'error': 'Доступ к комнате закрыт.'}, status=403)
    action = request.POST.get('action')
    own = lesson.participants.filter(identity=identity).first()
    if action in ('cancel_wait', 'leave'):
        if own:
            fields = {'hand_raised_at': None}
            if own.admission == 'waiting':
                fields['admission'] = 'left'
            lesson.participants.filter(pk=own.pk).update(**fields)
        return JsonResponse({'ok': True})
    if action in ('raise_hand', 'lower_hand'):
        target = request.POST.get('identity') or identity
        teacher = lesson_is_teacher(request, lesson)
        if target != identity and (not teacher or action != 'lower_hand'):
            return JsonResponse({'error': 'Нельзя менять руку другого участника.'}, status=403)
        if action == 'raise_hand':
            if not own or own.admission != 'admitted':
                return JsonResponse({'error': 'Сначала войдите в комнату.'}, status=409)
            try:
                if not participant_in_room(lesson, identity):
                    return JsonResponse({'error': 'Сначала войдите в комнату.'}, status=409)
            except LiveKitAPIError:
                return JsonResponse({'error': 'Не удалось проверить подключение.'}, status=503)
            lesson.participants.filter(pk=own.pk, hand_raised_at__isnull=True).update(
                hand_raised_at=timezone.now(), last_seen_at=timezone.now(),
            )
        else:
            lesson.participants.filter(identity=target).update(hand_raised_at=None)
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'Неизвестное действие.'}, status=400)


@login_required
@require_POST
@never_cache
def classroom_manage(request, public_id):
    lesson = teacher_lesson_or_404(request.user, public_id)
    if not room_available(lesson):
        return JsonResponse({'error': 'Управление доступно во время занятия.'}, status=409)
    action = request.POST.get('action')
    if action in ('admit', 'deny'):
        participant = lesson.participants.filter(identity=request.POST.get('identity'), admission='waiting',
                                                last_seen_at__gte=timezone.now() - PRESENCE_TTL).first()
        if not participant:
            return JsonResponse({'error': 'Участник уже вышел из ожидания или обработан.'}, status=409)
        if LiveLessonRemoval.objects.filter(lesson=lesson, identity=participant.identity).exists():
            return JsonResponse({'error': 'Этот участник удалён со встречи.'}, status=403)
        changed = lesson.participants.filter(pk=participant.pk, admission='waiting').update(
            admission='admitted' if action == 'admit' else 'denied',
        )
        if not changed:
            return JsonResponse({'error': 'Заявка уже обработана.'}, status=409)
        return JsonResponse({'ok': True})
    settings_fields = {'waiting_room': 'waiting_room_enabled', 'entry_locked': 'entry_locked',
                       'microphone': 'students_can_unmute', 'screen': 'students_can_share_screen'}
    if action not in (*settings_fields, 'mute_all'):
        return JsonResponse({'error': 'Неизвестное действие.'}, status=400)
    with transaction.atomic():
        lesson = teacher_lesson_or_404(request.user, public_id, for_update=True)
        if not room_available(lesson):
            return JsonResponse({'error': 'Занятие завершено.'}, status=409)
        if action == 'mute_all':
            lesson.mute_all_pending = True
            fields = ['mute_all_pending', 'updated_at']
        else:
            raw = request.POST.get('enabled')
            if raw not in ('true', 'false'):
                return JsonResponse({'error': 'Некорректная настройка.'}, status=400)
            field = settings_fields[action]
            setattr(lesson, field, raw == 'true')
            fields = [field, 'updated_at']
            if action == 'waiting_room' and raw == 'false':
                lesson.participants.filter(admission='waiting').update(admission='admitted')
            if action in ('microphone', 'screen'):
                lesson.policy_sync_until = timezone.now() + timedelta(minutes=5)
                fields.append('policy_sync_until')
        lesson.save(update_fields=fields)
    if action in ('microphone', 'screen', 'mute_all'):
        try:
            muted = sync_media_policy(lesson)
        except LiveKitAPIError:
            return JsonResponse({'ok': True, 'pending': True,
                                 'message': 'Настройка сохранена. Применим к участникам после восстановления медиасервера.'})
        return JsonResponse({'ok': True, 'muted': muted})
    return JsonResponse({'ok': True})
