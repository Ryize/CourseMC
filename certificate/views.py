from django.core.exceptions import PermissionDenied

from certificate.cert import create_certificate


def generate(request):
    if not request.user.is_staff:
        raise PermissionDenied()

    create_certificate('Чекашов Матвей', '12.11.2004', '1234567', )


def verify(request):
    pass
