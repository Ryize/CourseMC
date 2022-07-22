from django.urls import path

from .views import ScheduleViewSet, StudentViewSet, LearnGroupViewSet, ScheduleGet, StudentQuestionView

urlpatterns = [
    path('schedule/', ScheduleViewSet.as_view()),
    path('schedule/get_by_username/', ScheduleGet.as_view()),
    path('student/', StudentViewSet.as_view()),
    path('groups/', LearnGroupViewSet.as_view()),
    path('student_question/', StudentQuestionView.as_view()),
]
