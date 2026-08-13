from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def sync_course_feature_permissions(sender, **kwargs):
    """Новые разделы наследуют уже выданные роли для расписания и проверок."""

    if sender.label != 'Course':
        return

    permissions = {
        permission.codename: permission
        for permission in Permission.objects.filter(
            content_type__app_label='Course',
            content_type__model__in=(
                'curriculumversion',
                'curriculumlesson',
                'teachernotification',
            ),
        )
    }
    if not permissions:
        return

    for group in Group.objects.prefetch_related('permissions'):
        existing = {
            permission.codename
            for permission in group.permissions.all()
            if permission.content_type.app_label == 'Course'
        }
        additions = []
        for action in ('view', 'add', 'change', 'delete'):
            if f'{action}_schedule' in existing:
                for model in ('curriculumversion', 'curriculumlesson'):
                    permission = permissions.get(f'{action}_{model}')
                    if permission:
                        additions.append(permission)

        can_review = bool({
            'view_lessonsolution',
            'change_lessonsolution',
            'view_studentquestion',
            'change_studentquestion',
        }.intersection(existing))
        if can_review:
            for action in ('view', 'change'):
                permission = permissions.get(f'{action}_teachernotification')
                if permission:
                    additions.append(permission)

        if additions:
            group.permissions.add(*additions)
