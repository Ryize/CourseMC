from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from Course.models import Student


class StudentEmailAuthenticationBackend(ModelBackend):
    """Дополняет вход по e-mail для старых профилей CourseMC.

    Новые пользователи хранят e-mail в стандартной модели User. У части
    существующих учеников адрес остался только в модели Student, поэтому
    используем его как безопасный резервный идентификатор.
    """

    def authenticate(self, request, username=None, password=None, **credentials):
        email = credentials.get('email') or username
        if not email or not password:
            return None

        usernames = Student.objects.filter(
            email__iexact=email,
        ).values_list('name', flat=True)
        User = get_user_model()
        matched_user = None
        for user in User.objects.filter(username__in=usernames):
            if user.check_password(password) and self.user_can_authenticate(user):
                if matched_user:
                    return None
                matched_user = user
        return matched_user
