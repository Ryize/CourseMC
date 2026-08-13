from .models import TeacherNotification


def teacher_notifications(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    notifications = TeacherNotification.objects.filter(recipient=request.user)
    unread = notifications.filter(read_at__isnull=True)
    return {
        'teacher_notification_count': unread.count(),
        'teacher_notifications': list(unread[:5]),
    }
