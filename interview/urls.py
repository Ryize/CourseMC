from django.urls import path

from interview.views import test_answer

urlpatterns = [
    path("", test_answer, name="test_answer"),
]
