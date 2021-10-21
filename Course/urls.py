from django.urls import path

from Course.views import *

urlpatterns = [
    path('', StudentRecordView.as_view(), name='home'),
    path('schedule/', TimetableView.as_view(), name='schedule'),
]
