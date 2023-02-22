from django.core.exceptions import PermissionDenied
from django.utils import timezone

from Course.models import Student
from security.models import IPVisitors, BlockedIPAddress


class LastSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)
        if request.user.is_authenticated:
            student = Student.objects.filter(name=request.user.username).first()
            if student:
                student.last_session = timezone.now()
                student.save()

        return response


class IPVisitorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = request.META.get('REMOTE_ADDR')
        user = request.user
        visitors = IPVisitors.objects.filter(ip=ip).all()
        if visitors:
            visitors.delete()
        if user.is_authenticated:
            IPVisitors.objects.create(ip=ip, user=user)
        else:
            IPVisitors.objects.create(ip=ip)

        response = self.get_response(request)

        return response


class FilterIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        blocked_ips = BlockedIPAddress.objects.all()
        ip = request.META.get('REMOTE_ADDR')
        for blocked_ip in blocked_ips:
            if ip == blocked_ip.ip:
                raise PermissionDenied

        response = self.get_response(request)

        return response
