from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    """Cheap liveness probe used by Docker and Nginx."""

    return JsonResponse({"status": "ok"})


@require_GET
def readiness_check(request):
    """Readiness probe that also verifies database availability."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})


def page_not_found_view(request, url):
    return render(request, "errors/404.html", status=404)
