from django.urls import path

from .views import (LearnGroupViewSet, ScheduleGet, ScheduleViewSet,
                    StudentQuestionView, StudentViewSet, ClassesTimetableView,
                    ApplicationsForTrainingView)

urlpatterns = [
    path("schedule/", ScheduleViewSet.as_view()),
    path("schedule/get_by_username/", ScheduleGet.as_view()),
    path("student/", StudentViewSet.as_view()),
    path("groups/", LearnGroupViewSet.as_view()),
    path("student_question/", StudentQuestionView.as_view()),
    path("classes_timetable/<str:user_name>/", ClassesTimetableView.as_view()),
    path("app_training/", ApplicationsForTrainingView.as_view()),
]
