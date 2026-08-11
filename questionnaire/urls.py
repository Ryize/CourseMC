from django.urls import path

from questionnaire import views


urlpatterns = [
    path("", views.index, name="questionnaireIndex"),
    path("create_poll/", views.create_poll, name="create_poll"),
    path(
        "create_question/<int:quiz_id>/",
        views.create_question,
        name="create_question",
    ),
    path(
        "create_answer/<int:quiz_id>/",
        views.create_answer,
        name="create_answer",
    ),
    path(
        "poll/<int:quiz_id>/question/<int:question_id>/edit/",
        views.edit_question,
        name="edit_question",
    ),
    path(
        "poll/<int:quiz_id>/answer/<int:answer_id>/edit/",
        views.edit_answer,
        name="edit_answer",
    ),
    path(
        "create_answer/",
        views.create_answer_legacy,
        name="create_answer_legacy",
    ),
    path("my_polls/", views.QuizListView.as_view(), name="my_poll"),
    path(
        "poll/<int:quiz_id>/results/",
        views.poll_results,
        name="poll_results",
    ),
    path(
        "poll/<int:quiz_id>/archive/",
        views.archive_poll,
        name="archive_poll",
    ),
    path(
        "poll/<int:quiz_id>/restore/",
        views.restore_poll,
        name="restore_poll",
    ),
    path("go_poll/", views.go_poll, name="go_poll"),
    path("take_poll/<int:poll_id>/", views.take_poll, name="take_poll"),
    path("rating/<int:poll_id>/", views.rating, name="rating"),
]
