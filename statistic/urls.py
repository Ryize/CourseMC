from django.urls import path

from statistic.views import *

urlpatterns = [
    path("", statistic_index, name="home"),
]
