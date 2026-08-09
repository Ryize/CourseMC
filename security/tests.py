from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from CourseMC.middleware import FilterIPMiddleware, IPVisitorsMiddleware
from security.models import BlockedIPAddress, IPVisitors


def successful_response(request):
    return HttpResponse('ok')


class IPVisitorsMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = IPVisitorsMiddleware(successful_response)

    def request(self, ip='127.0.0.1', user=None):
        request = self.factory.get('/', REMOTE_ADDR=ip)
        request.user = user or AnonymousUser()
        return request

    def test_repeated_request_keeps_existing_visitor(self):
        self.middleware(self.request())
        visitor_id = IPVisitors.objects.get(ip='127.0.0.1').pk

        with self.assertNumQueries(1):
            response = self.middleware(self.request())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(IPVisitors.objects.count(), 1)
        self.assertEqual(
            IPVisitors.objects.get(ip='127.0.0.1').pk,
            visitor_id,
        )

    def test_existing_visitor_is_associated_with_authenticated_user(self):
        self.middleware(self.request())
        user = User.objects.create_user(username='middleware-user')

        self.middleware(self.request(user=user))

        visitor = IPVisitors.objects.get(ip='127.0.0.1')
        self.assertEqual(visitor.user, user)
        self.assertEqual(IPVisitors.objects.count(), 1)

    def test_request_without_ip_is_not_recorded(self):
        request = self.factory.get('/')
        request.META.pop('REMOTE_ADDR', None)
        request.user = AnonymousUser()

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(IPVisitors.objects.exists())

    def test_removed_last_session_middleware_is_not_configured(self):
        self.assertNotIn(
            'CourseMC.middleware.LastSessionMiddleware',
            settings.MIDDLEWARE,
        )


class FilterIPMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = FilterIPMiddleware(successful_response)

    def test_blocked_ip_is_rejected(self):
        BlockedIPAddress.objects.create(ip='203.0.113.10')
        request = self.factory.get('/', REMOTE_ADDR='203.0.113.10')

        with self.assertRaises(PermissionDenied):
            self.middleware(request)

    def test_allowed_ip_reaches_view(self):
        request = self.factory.get('/', REMOTE_ADDR='203.0.113.11')

        with self.assertNumQueries(1):
            response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
