import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasCourseMCBotToken(BasePermission):
    """Разрешает запрос только доверенному боту CourseMC."""

    message = 'Недействительный токен бота.'

    def has_permission(self, request, view):
        expected_token = settings.COURSEMC_BOT_API_TOKEN
        supplied_token = request.headers.get('X-CourseMC-Bot-Token', '')
        return bool(expected_token and supplied_token) and secrets.compare_digest(
            expected_token,
            supplied_token,
        )
