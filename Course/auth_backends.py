from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

class StudentEmailAuthenticationBackend(ModelBackend):
    """Дополняет вход по e-mail из канонической модели User."""

    def authenticate(self, request, username=None, password=None, **credentials):
        email = credentials.get('email') or username
        if not email or not password:
            return None

        User = get_user_model()
        matched_user = None
        users = User.objects.filter(email__iexact=email)
        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                if matched_user:
                    return None
                matched_user = user
        return matched_user
