from django.urls import path

from interview.views import question_progress, test_answer

urlpatterns = [
    path("", test_answer, name="test_answer"),
    path(
        "progress/<int:question_id>/",
        question_progress,
        name="interview_question_progress",
    ),
]
