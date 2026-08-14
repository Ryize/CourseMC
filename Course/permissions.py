from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


def sync_feature_permissions():
    """Добавляет ролям права, необходимые для связанных рабочих экранов."""

    target_permissions = {
        (permission.content_type.app_label, permission.codename): permission
        for permission in Permission.objects.filter(
            content_type__app_label__in=('Course', 'questionnaire'),
            content_type__model__in=(
                'directionstudy',
                'curriculumversion',
                'curriculumlesson',
                'teachernotification',
                'lessonsolutionsubmission',
                'passedpolls',
                'question',
                'useranswer',
            ),
        ).select_related('content_type')
    }
    if not target_permissions:
        return

    for group in Group.objects.prefetch_related('permissions__content_type'):
        existing = {
            (permission.content_type.app_label, permission.codename)
            for permission in group.permissions.all()
        }
        additions = []
        for action in ('view', 'add', 'change', 'delete'):
            if ('Course', f'{action}_schedule') in existing:
                for model in ('curriculumversion', 'curriculumlesson'):
                    permission = target_permissions.get(
                        ('Course', f'{action}_{model}'),
                    )
                    if permission:
                        additions.append(permission)

        for action in ('view', 'add', 'change'):
            if ('Course', f'{action}_schedule') in existing:
                permission = target_permissions.get(
                    ('Course', f'{action}_directionstudy'),
                )
                if permission:
                    additions.append(permission)

        can_review = bool({
            ('Course', 'view_lessonsolution'),
            ('Course', 'change_lessonsolution'),
            ('Course', 'view_studentquestion'),
            ('Course', 'change_studentquestion'),
        }.intersection(existing))
        if can_review:
            for action in ('view', 'change'):
                permission = target_permissions.get(
                    ('Course', f'{action}_teachernotification'),
                )
                if permission:
                    additions.append(permission)

        if ('Course', 'view_lessonsolution') in existing:
            permission = target_permissions.get(
                ('Course', 'view_lessonsolutionsubmission'),
            )
            if permission:
                additions.append(permission)

        if ('questionnaire', 'view_quiz') in existing:
            for model in ('passedpolls', 'question', 'useranswer'):
                permission = target_permissions.get(
                    ('questionnaire', f'view_{model}'),
                )
                if permission:
                    additions.append(permission)

        if additions:
            group.permissions.add(*additions)


@receiver(post_migrate)
def sync_course_feature_permissions(sender, **kwargs):
    sync_feature_permissions()
