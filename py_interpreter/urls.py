from django.urls import path

from py_interpreter.views import py_interpreter, solution_file_in_interpreter
from . import collaboration

urlpatterns = [
    path('python/lesson/<uuid:public_id>/', collaboration.shared_editor, name='shared_code_editor'),
    path('python/lesson/<uuid:public_id>/sync/', collaboration.shared_sync, name='shared_code_sync'),
    path('python/lesson/<uuid:public_id>/manage/', collaboration.shared_manage, name='shared_code_manage'),
    path('python/lesson/<uuid:public_id>/publish/', collaboration.shared_publish, name='shared_code_publish'),
    path('python/lesson/<uuid:public_id>/versions/<int:snapshot_id>/', collaboration.shared_snapshot,
         name='shared_code_snapshot'),
    path('python/materials/<int:attachment_id>/', collaboration.shared_attachment, name='shared_code_attachment'),
    path("python/", py_interpreter, name="py_interpreter"),
    path(
        "python/solution/<int:file_id>/",
        solution_file_in_interpreter,
        name="py_interpreter_solution_file",
    ),
]
