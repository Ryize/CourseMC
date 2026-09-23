from django.urls import path

from py_interpreter.views import py_interpreter, solution_file_in_interpreter

urlpatterns = [
    path("python/", py_interpreter, name="py_interpreter"),
    path(
        "python/solution/<int:file_id>/",
        solution_file_in_interpreter,
        name="py_interpreter_solution_file",
    ),
]
