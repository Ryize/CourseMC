from django.http import JsonResponse, HttpResponse
from django.shortcuts import render


class Error500:
    def __init__(self, response):
        self._get_response = response

    def __call__(self, request):
        return self._get_response(request)

    def process_exception(self, request, exception):
        return render(request, 'errors/404.html', status=404)
