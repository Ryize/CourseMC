from django.urls import path, include

from .views import ScheduleViewSet, StudentViewSet

urlpatterns = [
    path('schedule/', ScheduleViewSet.as_view()),
    path('student/', StudentViewSet.as_view()),
]
