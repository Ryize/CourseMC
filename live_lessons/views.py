import time
import re
import shutil
from datetime import timedelta
from tempfile import TemporaryFile
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

import jwt
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from Course.models import LearnGroup, Student
from Course.views import get_accessible_schedule_ids

from .chat import MAX_ATTACHMENT_BYTES, MAX_MESSAGE_LENGTH, message_payload, validate_attachment
from .archives import archive_filename, save_bundle
from .forms import DATETIME_FORMAT, LiveLessonChatArchiveForm, LiveLessonCreateForm, LiveLessonRescheduleForm
from .guests import guest_for_lesson
from .media import LiveKitAPIError, participant_identity, participant_in_room, room_service
from .models import (LiveLesson, LiveLessonAttachment, LiveLessonChatArchive,
                     LiveLessonMessage, LiveLessonRemoval, LiveLessonReschedule)


@require_GET
@never_cache
def quality_lab(request):
    """Изолированный от продакшена стенд проверки качества WebRTC."""
    if not settings.DEBUG:
        raise Http404
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    response = render(request, 'live_lessons/quality_lab.html')
    response['X-Robots-Tag'] = 'noindex, nofollow'
    response['Referrer-Policy'] = 'no-referrer'
    return response


def accessible_lessons(user):
    """Занятия ведущего и ученика любой из назначенных групп."""
    return LiveLesson.objects.filter(
        Q(audience=LiveLesson.Audience.OPEN, teacher__user=user) |
        Q(audience=LiveLesson.Audience.GROUPS, group__teacher__user=user) |
        Q(audience=LiveLesson.Audience.GROUPS, group__students__user=user,
          group__students__is_learned=True) |
        Q(audience=LiveLesson.Audience.GROUPS, additional_groups__students__user=user,
          additional_groups__students__is_learned=True,
          additional_groups__is_studies=True),
    ).select_related('group__teacher__user', 'teacher__user', 'curriculum_lesson').prefetch_related(
        'additional_groups',
    ).distinct()


def lesson_for_request(request, public_id):
    lesson = get_object_or_404(
        LiveLesson.objects.select_related('group', 'teacher__user').prefetch_related('additional_groups'),
        public_id=public_id,
    )
    if lesson.audience == LiveLesson.Audience.OPEN:
        return lesson
    if not request.user.is_authenticated:
        return None
    if not accessible_lessons(request.user).filter(pk=lesson.pk).exists():
        raise Http404
    return lesson


def room_available(lesson):
    if lesson.status != LiveLesson.Status.LIVE:
        return False
    if lesson.audience == LiveLesson.Audience.OPEN:
        return True
    return room_available_for_groups(lesson)


def room_available_for_groups(lesson):
    return bool(lesson.group_id and lesson.group.is_studies) or lesson.additional_groups.filter(
        is_studies=True,
    ).exists()


def teacher_lesson_or_404(user, public_id, *, for_update=False):
    queryset = LiveLesson.objects.select_related('group__teacher__user')
    if for_update:
        queryset = queryset.select_for_update(of=('self',))
    return get_object_or_404(queryset.filter(
        Q(audience=LiveLesson.Audience.OPEN, teacher__user=user) |
        Q(audience=LiveLesson.Audience.GROUPS, group__teacher__user=user),
    ), public_id=public_id)


@login_required
@require_GET
@never_cache
def lesson_list(request):
    lessons = accessible_lessons(request.user)
    return render(request, 'live_lessons/lesson_list.html', {
        'current_lessons': lessons.filter(
            status__in=(LiveLesson.Status.SCHEDULED, LiveLesson.Status.LIVE),
        ).order_by('scheduled_at', 'pk'),
        'past_lessons': lessons.filter(
            status__in=(LiveLesson.Status.ENDED, LiveLesson.Status.CANCELLED),
        ).order_by('-scheduled_at', '-pk')[:30],
        'can_create': LearnGroup.objects.filter(teacher__user=request.user).exists(),
    })


@login_required
@require_http_methods(['GET', 'POST'])
@never_cache
def lesson_create(request):
    if not LearnGroup.objects.filter(teacher__user=request.user).exists():
        raise Http404
    form = LiveLessonCreateForm(
        request.POST or None, teacher_user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        lesson = form.save(commit=False)
        lesson.teacher = request.user.course_profile
        lesson.origin = LiveLesson.Origin.EXTRA
        lesson.save()
        if lesson.audience == LiveLesson.Audience.GROUPS:
            lesson.additional_groups.set(form.cleaned_data['additional_groups'])
        messages.success(request, 'Занятие создано. Ссылку можно отправить участникам.')
        return redirect('live_lesson_detail', public_id=lesson.public_id)
    return render(request, 'live_lessons/lesson_form.html', {
        'form': form, 'heading': 'Новое занятие', 'submit_label': 'Создать занятие',
        'help_text': 'Выберите группы для закрытого занятия или создайте открытое по ссылке.',
    })


@require_GET
@never_cache
def lesson_detail(request, public_id):
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        return redirect_to_login(request.get_full_path())
    guest = guest_for_lesson(request, lesson) if (
        lesson.audience == LiveLesson.Audience.OPEN and not request.user.is_authenticated
    ) else None
    is_teacher = (lesson.teacher.user_id == request.user.pk if lesson.audience == LiveLesson.Audience.OPEN
                  else lesson.group.teacher.user_id == request.user.pk)
    archive_form = None
    if is_teacher and lesson.audience == LiveLesson.Audience.GROUPS and lesson.status in (
        LiveLesson.Status.LIVE, LiveLesson.Status.ENDED,
    ):
        archive_form = LiveLessonChatArchiveForm(lesson=lesson, teacher_user=request.user)
    return render(request, 'live_lessons/lesson_detail.html', {
        'lesson': lesson,
        'is_teacher': is_teacher,
        'archive_form': archive_form,
        'has_chat_messages': lesson.chat_messages.exists() if archive_form else False,
        'chat_archives': lesson.chat_archives.select_related('group', 'schedule').all() if is_teacher else (),
        'room_open': room_available(lesson),
        'guest_name': guest['name'] if guest else None,
        'chat_user_id': f"guest:{guest['id'].hex}" if guest else request.user.pk,
        'lesson_url': request.build_absolute_uri(reverse(
            'live_lesson_detail', kwargs={'public_id': lesson.public_id},
        )),
        'reschedules': lesson.reschedules.select_related('changed_by').all(),
        'show_chat': room_available(lesson) or lesson.status == LiveLesson.Status.ENDED,
    })


@login_required
@require_POST
@never_cache
def lesson_save_chat_archive(request, public_id):
    lesson = teacher_lesson_or_404(request.user, public_id)
    if lesson.audience != LiveLesson.Audience.GROUPS or lesson.status not in (
        LiveLesson.Status.LIVE, LiveLesson.Status.ENDED,
    ):
        raise Http404
    form = LiveLessonChatArchiveForm(request.POST, lesson=lesson, teacher_user=request.user)
    if not form.is_valid():
        messages.error(request, 'Выберите урок программы участвовавшей группы.')
        return redirect('live_lesson_detail', public_id=public_id)
    chat_rows = list(LiveLessonMessage.objects.filter(lesson=lesson)
                     .select_related('author', 'attachment').order_by('pk'))
    if not chat_rows:
        messages.error(request, 'В чате пока нет сообщений для сохранения.')
        return redirect('live_lesson_detail', public_id=public_id)
    group, schedule = form.target_objects()
    if LiveLessonChatArchive.objects.filter(
        lesson=lesson, group=group, schedule=schedule, last_message_id=chat_rows[-1].pk,
    ).exists():
        messages.info(request, 'Эта версия истории уже сохранена в выбранном уроке.')
        return redirect('live_lesson_detail', public_id=public_id)
    with transaction.atomic():
        archive = LiveLessonChatArchive.objects.create(
            lesson=lesson, group=group, schedule=schedule, created_by=request.user,
            last_message_id=chat_rows[-1].pk,
        )
        lines = [
            f'История чата: {lesson.title}',
            f'Группа: {group.title}',
            f'Урок программы: {schedule.theme}',
            f'Сохранено: {timezone.localtime().strftime("%d.%m.%Y %H:%M")}',
            '',
            'Ссылки на файлы открываются только преподавателю и участникам этой группы.',
            '',
        ]
        for item in chat_rows:
            author = (item.author.get_full_name().strip() or item.author.username) if item.author else item.guest_name
            author = re.sub(r'[\r\n\t]+', ' ', author)
            lines.append(f'[{timezone.localtime(item.created_at).strftime("%d.%m.%Y %H:%M")}] {author}')
            if item.body:
                lines.extend(f'  {line}' for line in item.body.splitlines())
            attachment = getattr(item, 'attachment', None)
            if attachment:
                file_url = request.build_absolute_uri(reverse(
                    'live_lesson_archive_attachment', args=[archive.pk, attachment.pk],
                ))
                safe_name = re.sub(r'[\r\n\t]+', ' ', attachment.original_name)
                lines.extend((f'  Файл: {safe_name}',
                              f'  В архиве: {archive_filename(item.pk, attachment.original_name)}',
                              f'  Ссылка: {file_url}'))
            lines.append('')
        try:
            save_bundle(archive, ('\n'.join(lines) + '\n').encode('utf-8'), chat_rows)
        except OSError:
            messages.error(request, 'Не удалось прикрепить один из файлов чата. Проверьте, что исходный файл доступен.')
            transaction.set_rollback(True)
            return redirect('live_lesson_detail', public_id=public_id)
    messages.success(request, f'История чата сохранена для группы «{group.title}» в уроке «{schedule.theme}».')
    return redirect('live_lesson_detail', public_id=public_id)


def _archive_for_user_or_404(user, archive_id):
    archive = get_object_or_404(
        LiveLessonChatArchive.objects.select_related('lesson__teacher__user', 'group', 'schedule'),
        pk=archive_id,
    )
    if archive.lesson.teacher.user_id == user.pk or archive.created_by_id == user.pk:
        return archive
    student = Student.objects.for_user(user)
    if (student and student.is_learned and student.groups_id == archive.group_id
            and not archive.schedule.is_archived
            and archive.schedule_id in get_accessible_schedule_ids(student)):
        return archive
    raise Http404


def _private_chat_response(opened_file, filename, *, content_type):
    response = FileResponse(opened_file, as_attachment=True, filename=filename, content_type=content_type)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['Referrer-Policy'] = 'no-referrer'
    return response


def _private_chat_file_response(file_field, filename, *, content_type):
    try:
        opened_file = file_field.open('rb')
    except FileNotFoundError:
        raise Http404 from None
    return _private_chat_response(opened_file, filename, content_type=content_type)


def _archive_chat_rows(archive):
    return LiveLessonMessage.objects.filter(
        lesson=archive.lesson, pk__lte=archive.last_message_id,
    ).select_related('author', 'attachment').order_by('pk')


def _ensure_archive_bundle(archive):
    if archive.file.name.lower().endswith('.zip'):
        return archive
    # Ранее сохранённые текстовые истории превращаем в полноценный архив при первом доступе.
    with transaction.atomic():
        archive = LiveLessonChatArchive.objects.select_for_update().get(pk=archive.pk)
        if not archive.file.name.lower().endswith('.zip'):
            archive.file.open('rb')
            try:
                transcript = archive.file.read()
            finally:
                archive.file.close()
            save_bundle(archive, transcript, _archive_chat_rows(archive))
    return archive


@login_required
@require_GET
@never_cache
def lesson_chat_archive_view(request, archive_id):
    archive = _archive_for_user_or_404(request.user, archive_id)
    context = {'archive': archive, 'chat_rows': _archive_chat_rows(archive)}
    template = ('live_lessons/_archive_chat.html' if request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                else 'live_lessons/archive_detail.html')
    response = render(request, template, context)
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@login_required
@require_GET
@never_cache
def lesson_chat_archive_download(request, archive_id):
    archive = _archive_for_user_or_404(request.user, archive_id)
    try:
        archive = _ensure_archive_bundle(archive)
    except OSError:
        return JsonResponse({'error': 'Не удалось собрать архив: исходный файл недоступен.'}, status=409)
    return _private_chat_file_response(
        archive.file, f'chat-lesson-{archive.schedule_id}-{archive.pk}.zip',
        content_type='application/zip',
    )


@login_required
@require_GET
@never_cache
def lesson_chat_archive_attachment(request, archive_id, attachment_id):
    archive = _archive_for_user_or_404(request.user, archive_id)
    attachment = get_object_or_404(
        LiveLessonAttachment.objects.select_related('message'),
        pk=attachment_id, message__lesson=archive.lesson,
        message_id__lte=archive.last_message_id,
    )
    try:
        archive = _ensure_archive_bundle(archive)
        archive.file.open('rb')
        temporary = TemporaryFile()
        try:
            with ZipFile(archive.file) as bundle:
                with bundle.open(archive_filename(attachment.message_id, attachment.original_name)) as source:
                    shutil.copyfileobj(source, temporary, length=1024 * 1024)
        except (BadZipFile, KeyError, OSError):
            temporary.close()
            raise Http404 from None
        finally:
            archive.file.close()
        temporary.seek(0)
    except OSError:
        raise Http404 from None
    return _private_chat_response(
        temporary, attachment.original_name, content_type='application/octet-stream',
    )


@login_required
@require_http_methods(['GET', 'POST'])
@never_cache
def lesson_reschedule(request, public_id):
    lesson = teacher_lesson_or_404(request.user, public_id)
    if lesson.status != LiveLesson.Status.SCHEDULED:
        raise Http404
    form = LiveLessonRescheduleForm(
        request.POST or None,
        initial={'scheduled_at': timezone.localtime(lesson.scheduled_at).strftime(DATETIME_FORMAT)},
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            lesson = teacher_lesson_or_404(request.user, public_id, for_update=True)
            if lesson.status != LiveLesson.Status.SCHEDULED:
                raise Http404
            new_time = form.cleaned_data['scheduled_at']
            if new_time != lesson.scheduled_at:
                LiveLessonReschedule.objects.create(
                    lesson=lesson, old_scheduled_at=lesson.scheduled_at,
                    new_scheduled_at=new_time, reason=form.cleaned_data['reason'],
                    changed_by=request.user,
                )
                lesson.scheduled_at = new_time
                lesson.save(update_fields=('scheduled_at', 'updated_at'))
                messages.success(request, 'Новое время занятия сохранено.')
            else:
                messages.info(request, 'Время занятия не изменилось.')
        return redirect('live_lesson_detail', public_id=lesson.public_id)
    return render(request, 'live_lessons/lesson_form.html', {
        'form': form, 'heading': 'Перенести занятие', 'submit_label': 'Сохранить время',
        'help_text': f'{lesson.title} · {lesson.group.title if lesson.group_id else "Открытый урок"}',
    })


@login_required
@require_POST
@never_cache
def lesson_change_status(request, public_id, action):
    transitions = {
        'start': (LiveLesson.Status.SCHEDULED, LiveLesson.Status.LIVE),
        'end': (LiveLesson.Status.LIVE, LiveLesson.Status.ENDED),
        'cancel': (LiveLesson.Status.SCHEDULED, LiveLesson.Status.CANCELLED),
    }
    if action not in transitions:
        raise Http404
    with transaction.atomic():
        lesson = teacher_lesson_or_404(request.user, public_id, for_update=True)
        previous, next_status = transitions[action]
        if lesson.status != previous or (action == 'start' and lesson.audience == LiveLesson.Audience.GROUPS
                                         and not room_available_for_groups(lesson)):
            raise Http404
        lesson.status = next_status
        fields = ['status', 'updated_at']
        if action == 'start':
            lesson.started_at = timezone.now()
            fields.append('started_at')
        elif action == 'end':
            lesson.ended_at = timezone.now()
            fields.append('ended_at')
        lesson.save(update_fields=fields)
    messages.success(request, {
        'start': 'Занятие начато.', 'end': 'Занятие завершено.',
        'cancel': 'Занятие отменено.',
    }[action])
    return redirect('live_lesson_detail', public_id=lesson.public_id)


@require_POST
@never_cache
def lesson_join_token(request, public_id):
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        return redirect_to_login(request.get_full_path())
    if not room_available(lesson):
        return JsonResponse({'error': 'Занятие сейчас недоступно.'}, status=409)
    identity = participant_identity(request, lesson)
    if LiveLessonRemoval.objects.filter(lesson=lesson, identity=identity).exists():
        return JsonResponse({'error': 'Преподаватель удалил вас из этого занятия.'}, status=403)

    server_url = settings.LIVEKIT_URL
    api_key = settings.LIVEKIT_API_KEY
    api_secret = settings.LIVEKIT_API_SECRET
    try:
        parsed = urlsplit(server_url)
        valid_url = (
            parsed.scheme in ('ws', 'wss') and bool(parsed.hostname) and
            not (parsed.username or parsed.password or parsed.query or parsed.fragment) and
            (parsed.scheme == 'wss' or (
                settings.DEBUG and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
            ))
        )
    except ValueError:
        valid_url = False
    if not (valid_url and api_key and api_secret and (settings.DEBUG or len(api_secret) >= 32)):
        return JsonResponse({'error': 'Медиасервер ещё не настроен.'}, status=503)

    now = int(time.time())
    if request.user.is_authenticated:
        participant_name = request.user.get_full_name().strip() or request.user.username
        participant_id = identity
    else:
        guest = guest_for_lesson(request, lesson)
        participant_name = guest['name']
        participant_id = identity
    token = jwt.encode({
        'iss': api_key,
        'sub': participant_id,
        'name': participant_name,
        'nbf': now,
        'exp': now + 5 * 60,
        'video': {
            'roomJoin': True,
            'room': lesson.room_name,
            'canPublish': True,
            'canSubscribe': True,
            'canPublishData': True,
        },
    }, api_secret, algorithm='HS256')
    response = JsonResponse({'server_url': server_url, 'participant_token': token})
    response['Cache-Control'] = 'no-store'
    response['Pragma'] = 'no-cache'
    response['Referrer-Policy'] = 'no-referrer'
    return response


@require_GET
@never_cache
def lesson_state(request, public_id):
    """Позволяет открытой комнате заметить завершение урока или отзыв доступа."""
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        return redirect_to_login(request.get_full_path())
    removed = LiveLessonRemoval.objects.filter(
        lesson=lesson, identity=participant_identity(request, lesson),
    ).exists() if room_available(lesson) else False
    response = JsonResponse({
        'status': lesson.status,
        'can_join': room_available(lesson) and not removed,
        'removed': removed,
    })
    response['Referrer-Policy'] = 'no-referrer'
    return response


@login_required
@require_POST
@never_cache
def lesson_moderate_participant(request, public_id):
    lesson = teacher_lesson_or_404(request.user, public_id)
    if not room_available(lesson):
        return JsonResponse({'error': 'Занятие сейчас недоступно.'}, status=409)
    action = request.POST.get('action')
    identity = request.POST.get('identity', '')
    if action not in ('mute', 'remove') or not re.fullmatch(
        r'(?:course-user-[1-9][0-9]*|lesson-guest-[0-9a-f]{32})', identity,
    ):
        return JsonResponse({'error': 'Некорректный участник или действие.'}, status=400)
    if identity in (f'course-user-{request.user.pk}', f'course-user-{lesson.teacher.user_id}'):
        return JsonResponse({'error': 'Преподавателя нельзя отключить этим действием.'}, status=403)
    payload = {'room': lesson.room_name, 'identity': identity}
    try:
        participant = room_service(lesson, 'GetParticipant', payload)
        if action == 'mute':
            microphone = next((track for track in participant.get('tracks', [])
                               if track.get('source') in ('MICROPHONE', 2) and track.get('sid')
                               and not track.get('muted')), None)
            if not microphone:
                return JsonResponse({'error': 'Микрофон участника уже выключен.'}, status=409)
            room_service(lesson, 'MutePublishedTrack', {
                **payload, 'track_sid': microphone['sid'], 'muted': True,
            })
        else:
            room_service(lesson, 'RemoveParticipant', payload)
            LiveLessonRemoval.objects.get_or_create(
                lesson=lesson, identity=identity, defaults={'removed_by': request.user},
            )
    except LiveKitAPIError as error:
        status = 409 if error.status_code == 404 else 503
        return JsonResponse({'error': ('Участник уже вышел из комнаты.' if status == 409 else str(error))},
                            status=status)
    return JsonResponse({'ok': True})


def _chat_cursor(request):
    after, before = request.GET.get('after'), request.GET.get('before')
    if after is not None and before is not None:
        return None, None, False
    value = after if after is not None else before
    if value is not None and (not value.isdecimal() or len(value) > 18):
        return None, None, False
    return int(after) if after is not None else None, int(before) if before is not None else None, True


@require_GET
@never_cache
def lesson_chat_messages(request, public_id):
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        return redirect_to_login(request.get_full_path())
    if lesson.status not in (LiveLesson.Status.LIVE, LiveLesson.Status.ENDED):
        return JsonResponse({'error': 'Чат пока недоступен.'}, status=409)
    if lesson.status == LiveLesson.Status.LIVE:
        try:
            if not participant_in_room(lesson, participant_identity(request, lesson)):
                return JsonResponse({'error': 'Сначала войдите в комнату.'}, status=409)
        except LiveKitAPIError:
            return JsonResponse({'error': 'Не удалось проверить подключение к комнате.'}, status=503)
    after, before, valid = _chat_cursor(request)
    if not valid:
        return JsonResponse({'error': 'Некорректная страница истории.'}, status=400)
    messages_query = LiveLessonMessage.objects.filter(lesson=lesson).select_related('author', 'attachment')
    if after is not None:
        page = list(messages_query.filter(pk__gt=after).order_by('pk')[:51])
    else:
        page = list(messages_query.filter(pk__lt=before).order_by('-pk')[:51] if before is not None
                    else messages_query.order_by('-pk')[:51])
    has_more = len(page) > 50
    page = page[:50]
    if after is None:
        page.reverse()
    response = JsonResponse({'messages': [message_payload(item) for item in page], 'has_more': has_more})
    response['Referrer-Policy'] = 'no-referrer'
    return response


@require_POST
@never_cache
def lesson_chat_send(request, public_id):
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        return redirect_to_login(request.get_full_path())
    if not room_available(lesson):
        return JsonResponse({'error': 'Отправка сообщений доступна только во время занятия.'}, status=409)
    identity = participant_identity(request, lesson)
    if LiveLessonRemoval.objects.filter(lesson=lesson, identity=identity).exists():
        return JsonResponse({'error': 'Преподаватель удалил вас из этого занятия.'}, status=403)
    try:
        if not participant_in_room(lesson, identity):
            return JsonResponse({'error': 'Сначала войдите в комнату.'}, status=409)
    except LiveKitAPIError:
        return JsonResponse({'error': 'Не удалось проверить подключение к комнате.'}, status=503)
    try:
        content_length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        content_length = 0
    if content_length > MAX_ATTACHMENT_BYTES + 1_000_000:
        return JsonResponse({'error': 'Файл слишком большой (максимум 25 МБ).'}, status=413)
    body = request.POST.get('body', '').strip()
    attachments = request.FILES.getlist('attachment')
    if len(body) > MAX_MESSAGE_LENGTH:
        return JsonResponse({'error': 'Сообщение слишком длинное (максимум 3000 символов).'}, status=400)
    if len(attachments) > 1 or (not body and not attachments):
        return JsonResponse({'error': 'Введите сообщение или выберите один файл.'}, status=400)
    if attachments:
        try:
            original_name, content_type = validate_attachment(attachments[0])
        except ValidationError as error:
            return JsonResponse({'error': error.messages[0]}, status=400)
    guest = guest_for_lesson(request, lesson) if not request.user.is_authenticated else None
    if guest:
        recent_messages = LiveLessonMessage.objects.filter(
            lesson=lesson, guest_id=guest['id'], created_at__gte=timezone.now() - timedelta(minutes=1),
        )
        if recent_messages.count() >= 20:
            return JsonResponse({'error': 'Слишком много сообщений. Попробуйте через минуту.'}, status=429)
        if attachments and LiveLessonAttachment.objects.filter(
            message__lesson=lesson, message__guest_id=guest['id'],
            message__created_at__gte=timezone.now() - timedelta(hours=1),
        ).count() >= 3:
            return JsonResponse({'error': 'Можно отправить не больше трёх файлов в час.'}, status=429)
    with transaction.atomic():
        message = LiveLessonMessage.objects.create(
            lesson=lesson, author=request.user if request.user.is_authenticated else None,
            guest_id=guest['id'] if guest else None, guest_name=guest['name'] if guest else '', body=body,
        )
        if attachments:
            LiveLessonAttachment.objects.create(
                message=message, file=attachments[0], original_name=original_name,
                content_type=content_type, size=attachments[0].size,
            )
    response = JsonResponse({'message': message_payload(message)}, status=201)
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response


@require_GET
@never_cache
def lesson_chat_attachment(request, public_id, attachment_id):
    lesson = lesson_for_request(request, public_id)
    if lesson is None:
        return redirect_to_login(request.get_full_path())
    if lesson.status == LiveLesson.Status.LIVE:
        try:
            if not participant_in_room(lesson, participant_identity(request, lesson)):
                raise Http404
        except LiveKitAPIError:
            return JsonResponse({'error': 'Не удалось проверить подключение к комнате.'}, status=503)
    attachment = get_object_or_404(
        LiveLessonAttachment.objects.select_related('message'),
        pk=attachment_id, message__lesson=lesson,
    )
    try:
        file = attachment.file.open('rb')
    except FileNotFoundError:
        raise Http404 from None
    response = FileResponse(file, as_attachment=True, filename=attachment.original_name,
                            content_type='application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['Referrer-Policy'] = 'no-referrer'
    return response
