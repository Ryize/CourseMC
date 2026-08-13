from django.db.models import Exists, OuterRef

from .models import LearnGroup, Student


def sync_group_activity(group_ids=None):
    """Синхронизирует статус групп с наличием действующих учеников."""

    groups = LearnGroup.objects.all()
    if group_ids is not None:
        group_ids = {group_id for group_id in group_ids if group_id}
        if not group_ids:
            return
        groups = groups.filter(pk__in=group_ids)

    active_students = Student.objects.filter(
        groups_id=OuterRef('pk'),
        is_learned=True,
    )
    groups.filter(Exists(active_students)).exclude(is_studies=True).update(
        is_studies=True,
    )
    groups.filter(~Exists(active_students)).exclude(is_studies=False).update(
        is_studies=False,
    )
