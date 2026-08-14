from django.core.exceptions import PermissionDenied

from security.models import IPVisitors, BlockedIPAddress


PROBE_PATHS = {'/health/', '/ready/'}


def get_client_ip(request):
    """Return the address set by the trusted Nginx proxy when available."""

    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR')


class IPVisitorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in PROBE_PATHS:
            return self.get_response(request)

        ip = get_client_ip(request)
        if ip:
            user_id = (
                request.user.pk if request.user.is_authenticated else None
            )
            visitor = (
                IPVisitors.objects
                .filter(ip=ip)
                .only('id', 'user_id')
                .first()
            )

            if visitor is None:
                IPVisitors.objects.create(ip=ip, user_id=user_id)
            elif visitor.user_id != user_id:
                IPVisitors.objects.filter(pk=visitor.pk).update(
                    user_id=user_id
                )

        return self.get_response(request)


class FilterIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in PROBE_PATHS:
            return self.get_response(request)

        ip = get_client_ip(request)
        if ip and BlockedIPAddress.objects.filter(ip=ip).exists():
            raise PermissionDenied

        return self.get_response(request)
