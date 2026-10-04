"""An authoritative, persistent Yjs-compatible document. No Python execution here."""
import base64
import binascii
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import OperationalError, transaction
from django.db.models import F
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from pycrdt import Doc, Text

from live_lessons.media import LiveKitAPIError, participant_identity, participant_in_room
from live_lessons.models import LiveLesson, LiveLessonParticipant, LiveLessonRemoval
from Course.models import Student
from Course.views import get_accessible_schedule_ids
from live_lessons.views import lesson_for_request, lesson_is_teacher, room_available, wants_json
from .forms import SharedCodePublishForm
from .models import SharedCodeAttachment, SharedCodeDocument, SharedCodeParticipant, SharedCodeSnapshot

DEFAULT_CODE = 'def main():\n    print("Hello, CourseMC!")\n\n\nmain()\n'
MAX_CODE = 20000  # UTF-16 units, the same limit as Ace / JavaScript.
MAX_UPDATE = 96 * 1024
MAX_STATE = 512 * 1024
PRESENCE_TTL = timedelta(seconds=20)
VERIFY_TTL = timedelta(seconds=8)


def document_from_state(state=None):
    doc = Doc({'code': Text()})
    if state:
        doc.apply_update(bytes(state))
    return doc


def encoded(value):
    return base64.b64encode(value).decode('ascii')


def decoded(value, limit):
    if not isinstance(value, str) or len(value) > (limit * 4 // 3 + 4):
        raise ValueError('Некорректный размер данных.')
    try:
        result = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('Некорректные данные редактора.') from None
    if len(result) > limit:
        raise ValueError('Некорректный размер данных.')
    return result


def payload(request):
    if len(request.body) > 160 * 1024:
        raise ValueError('Запрос слишком большой.')
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeError):
        raise ValueError('Некорректный запрос.') from None
    if not isinstance(data, dict):
        raise ValueError('Некорректный запрос.')
    return data


def permitted_lesson(request, public_id):
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        raise PermissionDenied('Авторизуйтесь на платформе.')
    identity = participant_identity(request, lesson)
    if LiveLessonRemoval.objects.filter(lesson=lesson, identity=identity).exists():
        raise PermissionDenied('Доступ к занятию закрыт.')
    teacher = lesson_is_teacher(request, lesson)
    participant = lesson.participants.filter(identity=identity).first()
    # A shared document is available only to the host and admitted participants,
    # including on open lessons. A forwarded lesson link is not editor access.
    if not teacher and (not participant or participant.admission != 'admitted'):
        raise PermissionDenied('Сначала получите доступ к комнате.')
    return lesson, identity, teacher, participant


def error(message, status=400, **extra):
    return JsonResponse({'error': message, **extra}, status=status)


@require_GET
@never_cache
@ensure_csrf_cookie
@xframe_options_sameorigin
def shared_editor(request, public_id):
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        return redirect_to_login(request.get_full_path())
    lesson, _, teacher, _ = permitted_lesson(request, public_id)
    response = render(request, 'py_interpreter/py_interpreter.html', {
        'shared_lesson': lesson, 'shared_teacher': teacher,
        'embedded': request.GET.get('embedded') == '1',
        'source_code': '', 'download_name': 'lesson.py',
        'code_publish_form': SharedCodePublishForm(lesson=lesson, teacher_user=request.user,
                                                  current_code=True, auto_id='id_shared_code_%s')
                             if teacher and lesson.audience == LiveLesson.Audience.GROUPS else None,
    })
    response['Referrer-Policy'] = 'same-origin'
    return response


def presence_verified(lesson, identity, own):
    now = timezone.now()
    if own and own.verified_at and own.verified_at > now - VERIFY_TTL:
        return True, own.verified_at
    return participant_in_room(lesson, identity), now


def clean_cursor(raw):
    if not isinstance(raw, dict):
        raise ValueError('Некорректный курсор.')
    result = {}
    # Yjs relative positions remain attached to text as other people type.
    for key in ('anchor', 'head'):
        value = raw.get(key)
        if value is not None:
            decoded(value, 256)
            result[key] = value
    return result


def snapshot_payload(snapshot):
    return {'id': snapshot.pk, 'title': snapshot.title,
            'created_at': timezone.localtime(snapshot.created_at).strftime('%d.%m.%Y %H:%M'),
            'url': reverse('shared_code_snapshot', args=[snapshot.document.lesson.public_id, snapshot.pk])}


@require_POST
@never_cache
def shared_sync(request, public_id):
    try:
        data = payload(request)
        update = decoded(data.get('update', ''), MAX_UPDATE)
        vector = decoded(data.get('vector', ''), 8192)
        cursor = clean_cursor(data.get('cursor', {}))
    except ValueError as exc:
        return error(str(exc))
    lesson, identity, teacher, participant = permitted_lesson(request, public_id)
    active = room_available(lesson)
    document = SharedCodeDocument.objects.filter(lesson=lesson).first()
    if document is None:
        if not teacher or not active:
            return error('Преподаватель ещё не открыл общий редактор.', 404, code='not_started')
        initial = Doc({'code': Text(DEFAULT_CODE)})
        document, _ = SharedCodeDocument.objects.get_or_create(
            lesson=lesson, defaults={'state': initial.get_update(), 'code': DEFAULT_CODE},
        )
        type(lesson).objects.filter(pk=lesson.pk).update(updated_at=timezone.now())
    own = document.editors.filter(identity=identity).first()
    if active:
        try:
            connected, verified_at = presence_verified(lesson, identity, own)
        except LiveKitAPIError:
            return error('Не удалось проверить подключение. Повторяем…', 503)
        if not connected:
            return error('Редактор доступен после входа в звонок.', 409, code='not_connected')
    elif update:
        return error('Занятие завершено. Код доступен только для чтения.', 409, code='read_only')
    name = (request.user.get_full_name().strip() or request.user.username) if teacher else participant.name
    try:
        with transaction.atomic():
            # Acquire the writer before reading state. Also works with SQLite
            # where SELECT FOR UPDATE does not serialize competing writers.
            SharedCodeDocument.objects.filter(pk=document.pk).update(revision=F('revision') + 1)
            document.refresh_from_db()
            lesson.refresh_from_db()
            active = room_available(lesson)
            if update and not active:
                return error('Занятие завершено. Код доступен только для чтения.', 409, code='read_only')
            if lesson.removed_participants.filter(identity=identity).exists() or (
                not teacher and not lesson.participants.filter(identity=identity, admission='admitted').exists()
            ):
                return error('Доступ к редактору закрыт.', 403, code='read_only')
            # Permissions are reread under the same lock as accepting an update.
            own, _ = document.editors.get_or_create(identity=identity, defaults={'name': name})
            can_edit = active and (teacher or own.can_edit)
            if update and not can_edit:
                return error('Преподаватель не разрешил редактирование.', 403, code='read_only')
            doc = document_from_state(document.state)
            try:
                if update:
                    doc.apply_update(update)
                code = str(doc['code'])
                if set(doc.keys()) != {'code'} or any(not isinstance(item[0], str) or item[1]
                                                      for item in doc['code'].diff()):
                    raise ValueError('Допустим только обычный текст Python.')
                if len(code.encode('utf-16-le')) // 2 > MAX_CODE:
                    raise ValueError('Максимум 20 000 символов кода.')
                state = doc.get_update()
                if len(state) > MAX_STATE:
                    raise ValueError('Слишком много правок. Сохраните код и создайте новое занятие.')
                diff = doc.get_update(vector or None)
            except Exception as exc:
                transaction.set_rollback(True)
                return error(str(exc) if isinstance(exc, ValueError) else 'Некорректные данные редактора.',
                             code='invalid_update')
            if state != bytes(document.state):
                document.state, document.code, document.updated_at = state, code, timezone.now()
                document.save(update_fields=['state', 'code', 'updated_at'])
            if active:
                own.name, own.cursor = name, cursor
                own.last_seen_at, own.verified_at = timezone.now(), verified_at
                own.save(update_fields=['name', 'cursor', 'last_seen_at', 'verified_at'])
            removed = lesson.removed_participants.values_list('identity', flat=True)
            editors = document.editors.filter(last_seen_at__gte=timezone.now() - PRESENCE_TTL).exclude(identity__in=removed)
            people = [{'identity': item.identity, 'name': item.name,
                       'can_edit': item.can_edit or item.identity == f'course-user-{lesson.teacher.user_id}',
                       'cursor': item.cursor} for item in editors.order_by('pk')[:100]] if active else []
            if teacher:
                grants = {item.identity: item.can_edit for item in document.editors.all()}
                members = [{'identity': item.identity, 'name': item.name, 'can_edit': grants.get(item.identity, False)}
                           for item in lesson.participants.filter(admission='admitted').exclude(identity=identity)
                           .exclude(identity__in=removed).order_by('pk')[:100]]
            else:
                members = []
            return JsonResponse({'update': encoded(diff), 'vector': encoded(doc.get_state()),
                                 'identity': identity, 'can_edit': can_edit, 'teacher': teacher,
                                 'active': active, 'people': people, 'members': members,
                                 'snapshots': [snapshot_payload(item) for item in document.snapshots.all()[:20]]})
    except OperationalError:
        return error('Синхронизация занята. Повторяем…', 503)


@require_POST
@never_cache
def shared_manage(request, public_id):
    lesson, identity, teacher, _ = permitted_lesson(request, public_id)
    if not teacher:
        raise PermissionDenied
    try:
        data = payload(request)
    except ValueError as exc:
        return error(str(exc))
    document = get_object_or_404(SharedCodeDocument, lesson=lesson)
    action = data.get('action')
    if action == 'grant':
        if not room_available(lesson):
            return error('Занятие завершено.', 409)
        target = lesson.participants.filter(identity=data.get('identity'), admission='admitted').first()
        if not target or target.identity == identity or lesson.removed_participants.filter(identity=target.identity).exists():
            return error('Участник недоступен.', 404)
        if not isinstance(data.get('enabled'), bool):
            return error('Некорректное разрешение.')
        with transaction.atomic():
            SharedCodeDocument.objects.filter(pk=document.pk).update(revision=F('revision') + 1)
            document.editors.update_or_create(identity=target.identity,
                                             defaults={'name': target.name, 'can_edit': data['enabled']})
        return JsonResponse({'ok': True})
    if action == 'save':
        title = data.get('title', 'Код занятия')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
            return error('Название версии: от 1 до 100 символов.')
        # This immutable copy never changes when the shared document is edited.
        snapshot = document.snapshots.create(title=title.strip(), code=document.code, created_by=request.user)
        type(lesson).objects.filter(pk=lesson.pk).update(updated_at=timezone.now())
        return JsonResponse({'ok': True, 'snapshot': snapshot_payload(snapshot)})
    return error('Неизвестное действие.')


@require_GET
@never_cache
def shared_snapshot(request, public_id, snapshot_id):
    lesson, _, _, _ = permitted_lesson(request, public_id)
    snapshot = get_object_or_404(SharedCodeSnapshot, pk=snapshot_id, document__lesson=lesson)
    response = HttpResponse(snapshot.code, content_type='text/x-python; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="lesson-{snapshot.pk}.py"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@require_POST
@never_cache
def shared_publish(request, public_id):
    lesson, _, teacher, _ = permitted_lesson(request, public_id)
    if not teacher:
        raise PermissionDenied
    if lesson.audience != LiveLesson.Audience.GROUPS:
        return error('Прикрепить код к уроку программы можно только в групповом занятии.')
    is_json = request.content_type == 'application/json'
    try:
        data = payload(request) if is_json else request.POST
    except ValueError as exc:
        return error(str(exc))
    form = SharedCodePublishForm(data, lesson=lesson, teacher_user=request.user, current_code=is_json)
    if not form.is_valid():
        message = 'Выберите доступную версию кода, урок программы и свою группу.'
        if is_json or wants_json(request):
            return error(message)
        messages.error(request, message)
        return redirect('live_lesson_detail', public_id=public_id)
    try:
        with transaction.atomic():
            document = get_object_or_404(SharedCodeDocument, lesson=lesson)
            # Same writer lock as synchronization: copy only accepted server code.
            SharedCodeDocument.objects.filter(pk=document.pk).update(revision=F('revision') + 1)
            document.refresh_from_db()
            snapshot = form.cleaned_data['snapshot']
            if snapshot is None:
                title = form.cleaned_data['title']
                # Retry after a lost response must not create a duplicate file/version.
                snapshot = document.snapshots.filter(title=title, code=document.code).first()
                if snapshot is None:
                    snapshot = document.snapshots.create(title=title, code=document.code, created_by=request.user)
            group, schedule = form.target_objects()
            attachment, created = SharedCodeAttachment.objects.get_or_create(
                snapshot=snapshot, group=group, schedule=schedule, defaults={'created_by': request.user},
            )
            type(lesson).objects.filter(pk=lesson.pk).update(updated_at=timezone.now())
    except OperationalError:
        return error('Сохранение занято. Повторите попытку.', 503)
    message = (f'Файл прикреплён: {group.title} · {schedule.theme}.' if created
               else 'Эта версия файла уже прикреплена к выбранному уроку и группе.')
    if is_json or wants_json(request):
        return JsonResponse({'ok': True, 'message': message, 'snapshot': snapshot_payload(snapshot),
                             'attachment': {'id': attachment.pk, 'group': group.title,
                                            'schedule': schedule.theme,
                                            'url': reverse('shared_code_attachment', args=[attachment.pk])}})
    messages.success(request, message)
    return redirect('live_lesson_detail', public_id=public_id)


@login_required
@require_GET
@never_cache
def shared_attachment(request, attachment_id):
    attachment = get_object_or_404(SharedCodeAttachment.objects.select_related(
        'snapshot', 'group__teacher', 'schedule'), pk=attachment_id)
    allowed = request.user.pk in (attachment.created_by_id, attachment.group.teacher.user_id)
    if not allowed:
        student = Student.objects.for_user(request.user)
        allowed = (student and student.is_learned and student.groups_id == attachment.group_id
                   and not attachment.schedule.is_archived
                   and attachment.schedule_id in get_accessible_schedule_ids(student))
    if not allowed:
        raise Http404
    response = HttpResponse(attachment.snapshot.code, content_type='text/x-python; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="code-lesson-{attachment.schedule_id}-{attachment.pk}.py"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response
