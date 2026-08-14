from django.db.models import Count

from .models import TeacherNotification


def teacher_notifications(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    notifications = TeacherNotification.objects.filter(recipient=request.user)
    unread = notifications.filter(read_at__isnull=True)
    counts_by_kind = {
        row['kind']: row['total']
        for row in unread.values('kind').annotate(total=Count('pk'))
    }
    return {
        'teacher_notification_count': sum(counts_by_kind.values()),
        'teacher_notifications': list(unread[:5]),
        'lesson_solution_notification_count': counts_by_kind.get(
            TeacherNotification.Kind.LESSON_SOLUTION,
            0,
        ),
        'student_question_notification_count': counts_by_kind.get(
            TeacherNotification.Kind.STUDENT_QUESTION,
            0,
        ),
        'code_review_notification_count': counts_by_kind.get(
            TeacherNotification.Kind.CODE_REVIEW,
            0,
        ),
    }
