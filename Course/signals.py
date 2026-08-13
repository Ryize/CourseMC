from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from codereview.models import ProjectForReview

from .models import (
    LessonSolutionSubmission,
    LearnGroup,
    Student,
    StudentQuestion,
    TeacherNotification,
)
from .services import sync_group_activity


@receiver(pre_save, sender=Student)
def remember_previous_student_group(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_group_id = None
        return
    instance._previous_group_id = (
        sender.objects
        .filter(pk=instance.pk)
        .values_list('groups_id', flat=True)
        .first()
    )


@receiver(post_save, sender=Student)
def sync_student_groups_after_save(sender, instance, **kwargs):
    sync_group_activity(
        {instance.groups_id, getattr(instance, '_previous_group_id', None)},
    )


@receiver(post_delete, sender=Student)
def sync_student_group_after_delete(sender, instance, **kwargs):
    sync_group_activity({instance.groups_id})


@receiver(post_save, sender=LearnGroup)
def sync_new_group_activity(sender, instance, **kwargs):
    sync_group_activity({instance.pk})


def _create_notification(*, recipient_id, kind, title, message, url, event_key):
    if not recipient_id:
        return
    TeacherNotification.objects.get_or_create(
        event_key=event_key,
        defaults={
            'recipient_id': recipient_id,
            'kind': kind,
            'title': title,
            'message': message,
            'target_url': url,
        },
    )


@receiver(post_save, sender=LessonSolutionSubmission)
def notify_about_lesson_solution(sender, instance, created, **kwargs):
    if not created:
        return
    solution = instance.solution
    _create_notification(
        recipient_id=solution.student.groups.teacher.user_id,
        kind=TeacherNotification.Kind.LESSON_SOLUTION,
        title=f'Решение: {solution.schedule.theme}',
        message=f'{solution.student} отправил работу на проверку.',
        url=reverse(
            'admin:Course_lessonsolution_change',
            args=(solution.pk,),
        ),
        event_key=f'lesson-submission:{instance.pk}',
    )


@receiver(post_save, sender=StudentQuestion)
def notify_about_student_question(sender, instance, created, **kwargs):
    if not created:
        return
    _create_notification(
        recipient_id=instance.group.teacher.user_id,
        kind=TeacherNotification.Kind.STUDENT_QUESTION,
        title=f'Новый вопрос · {instance.group}',
        message=instance.question,
        url=reverse(
            'admin:Course_studentquestion_change',
            args=(instance.pk,),
        ),
        event_key=f'student-question:{instance.pk}',
    )


@receiver(post_save, sender=ProjectForReview)
def notify_about_code_review(sender, instance, created, **kwargs):
    if not created:
        return
    _create_notification(
        recipient_id=instance.user.groups.teacher.user_id,
        kind=TeacherNotification.Kind.CODE_REVIEW,
        title=f'Проект на ревью: {instance.category}',
        message=f'{instance.user} отправил проект на проверку.',
        url=reverse(
            'admin:codereview_projectforreview_change',
            args=(instance.pk,),
        ),
        event_key=f'project-review:{instance.pk}',
    )
