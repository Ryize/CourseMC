from django.urls import path

from interview.views import (
    mock_interview_analyze,
    mock_interview_abandon,
    mock_interview_live_coding,
    mock_interview_history,
    mock_interview_processing,
    mock_interview_result,
    mock_interview_resume,
    mock_interview_start,
    mock_interview_theory,
    mock_solution_file_download,
    mock_task_file_download,
    question_progress,
    test_answer,
)

urlpatterns = [
    path("", test_answer, name="test_answer"),
    path(
        "progress/<int:question_id>/",
        question_progress,
        name="interview_question_progress",
    ),
    path('mock/', mock_interview_start, name='mock_interview_start'),
    path(
        'mock/history/',
        mock_interview_history,
        name='mock_interview_history',
    ),
    path(
        'mock/<int:interview_id>/',
        mock_interview_resume,
        name='mock_interview_resume',
    ),
    path(
        'mock/<int:interview_id>/theory/',
        mock_interview_theory,
        name='mock_interview_theory',
    ),
    path(
        'mock/<int:interview_id>/abandon/',
        mock_interview_abandon,
        name='mock_interview_abandon',
    ),
    path(
        'mock/<int:interview_id>/live-coding/',
        mock_interview_live_coding,
        name='mock_interview_live_coding',
    ),
    path(
        'mock/<int:interview_id>/processing/',
        mock_interview_processing,
        name='mock_interview_processing',
    ),
    path(
        'mock/<int:interview_id>/analyze/',
        mock_interview_analyze,
        name='mock_interview_analyze',
    ),
    path(
        'mock/<int:interview_id>/result/',
        mock_interview_result,
        name='mock_interview_result',
    ),
    path(
        'mock/<int:interview_id>/task-file/',
        mock_task_file_download,
        name='mock_task_file_download',
    ),
    path(
        'mock/file/<int:file_id>/',
        mock_solution_file_download,
        name='mock_solution_file_download',
    ),
]
