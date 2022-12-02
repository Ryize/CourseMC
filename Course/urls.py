from django.urls import path

from Course.views import *

urlpatterns = [
    path("", StudentRecordView.as_view(), name="home"),
    path("schedule/", TimetableView.as_view(), name="schedule"),
    path("download_report/<int:group_id>", download_report, name="download_report"),
    path("get_training_program/", get_training_program, name="get_training_program"),
    path("ask_question/", ask_question, name="ask_question"),
    path("get_filter_data/", get_filter_data, name="get_filter_data"),
    path("create_group/", create_group, name="create_group"),
]
