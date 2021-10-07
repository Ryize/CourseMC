from django.urls import path, include

from .views import ScheduleViewSet, StudentViewSet, ScheduleUserViewSet

urlpatterns = [
    path('schedule/', ScheduleViewSet.as_view()),
    path('schedule/get_by_username', ScheduleUserViewSet.as_view()),
    path('student/', StudentViewSet.as_view()),
]
