from django.urls import path

from py_interpreter.views import *

urlpatterns = [
    path("python/", py_interpreter, name="py_interpreter"),
]
