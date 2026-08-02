from django.utils import timezone

from questionnaire.models import Quiz


def poll_is_active(poll: Quiz) -> bool:
    return poll.lifetime > timezone.now()
