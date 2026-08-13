from django.apps import AppConfig


class AuthConfig(AppConfig):
    name = "Course"
    verbose_name = "Про курс"

    def ready(self):
        from . import signals  # noqa: F401
        from . import permissions  # noqa: F401
