from django.utils import timezone

from questionnaire.models import Quiz


def poll_is_active(poll: Quiz) -> bool:
    return not poll.is_archived and poll.lifetime > timezone.now()
