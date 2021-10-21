from django.urls import path, include

from .views import ScheduleViewSet, StudentViewSet, LearnGroupViewSet, ScheduleGet

urlpatterns = [
    path('schedule/', ScheduleViewSet.as_view()),
    path('schedule/get_by_username/', ScheduleGet.as_view()),
    path('student/', StudentViewSet.as_view()),
    path('groups/', LearnGroupViewSet.as_view()),
]
