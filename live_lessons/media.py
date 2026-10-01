"""Server-side LiveKit room administration; API credentials never reach the browser."""

import time
from urllib.parse import urlsplit, urlunsplit

import jwt
import requests
from django.conf import settings


class LiveKitAPIError(Exception):
    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def room_service(lesson, method, payload):
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET or (
        not settings.DEBUG and len(settings.LIVEKIT_API_SECRET) < 32
    ):
        raise LiveKitAPIError('Медиасервер ещё не настроен.')
    public_url = urlsplit(settings.LIVEKIT_URL)
    api_url = urlsplit(settings.LIVEKIT_API_URL) if settings.LIVEKIT_API_URL else public_url
    if api_url.scheme not in ('http', 'https', 'ws', 'wss') or not api_url.hostname or (
        api_url.username or api_url.password or api_url.query or api_url.fragment
    ):
        raise LiveKitAPIError('Адрес медиасервера настроен неверно.')
    scheme = 'https' if api_url.scheme in ('https', 'wss') else 'http'
    endpoint = urlunsplit((scheme, api_url.netloc,
                           f"{api_url.path.rstrip('/')}/twirp/livekit.RoomService/{method}", '', ''))
    now = int(time.time())
    token = jwt.encode({
        'iss': settings.LIVEKIT_API_KEY, 'sub': 'coursemc-room-admin',
        'nbf': now, 'exp': now + 60,
        'video': ({'roomCreate': True} if method == 'DeleteRoom'
                  else {'roomAdmin': True, 'room': lesson.room_name}),
    }, settings.LIVEKIT_API_SECRET, algorithm='HS256')
    try:
        response = requests.post(endpoint, json=payload, timeout=5, headers={
            'Authorization': f'Bearer {token}',
        })
    except requests.RequestException as error:
        raise LiveKitAPIError('Не удалось связаться с медиасервером.') from error
    if not response.ok:
        raise LiveKitAPIError('Медиасервер не выполнил запрос.', status_code=response.status_code)
    try:
        return response.json()
    except ValueError as error:
        raise LiveKitAPIError('Медиасервер вернул некорректный ответ.') from error


def participant_identity(request, lesson):
    if request.user.is_authenticated:
        return f'course-user-{request.user.pk}'
    from .guests import guest_for_lesson
    guest = guest_for_lesson(request, lesson)
    return f"lesson-guest-{guest['id'].hex}"


def participant_in_room(lesson, identity):
    try:
        room_service(lesson, 'GetParticipant', {'room': lesson.room_name, 'identity': identity})
    except LiveKitAPIError as error:
        if error.status_code == 404:
            return False
        raise
    return True
