import os

from django.db.models import Exists, OuterRef
from django.http import FileResponse

from .models import LearnGroup, Student


def lesson_solution_file_response(solution_file, *, as_attachment=True):
    """Безопасно отдаёт файл решения с корректным типом содержимого."""
    response = FileResponse(
        solution_file.file.open('rb'),
        as_attachment=as_attachment,
        filename=solution_file.original_name,
    )
    if not as_attachment:
        extension = os.path.splitext(solution_file.original_name)[1].lower()
        if extension in {'.py', '.txt', '.md'}:
            response['Content-Type'] = 'text/plain; charset=utf-8'
        elif extension == '.ipynb':
            response['Content-Type'] = 'application/json; charset=utf-8'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def sync_group_activity(group_ids=None):
    """Синхронизирует статус групп с наличием действующих учеников."""

    groups = LearnGroup.objects.all()
    if group_ids is not None:
        group_ids = {group_id for group_id in group_ids if group_id}
        if not group_ids:
            return
        groups = groups.filter(pk__in=group_ids)

    active_students = Student.objects.filter(
        groups_id=OuterRef('pk'),
        is_learned=True,
    )
    groups.filter(Exists(active_students)).exclude(is_studies=True).update(
        is_studies=True,
    )
    groups.filter(~Exists(active_students)).exclude(is_studies=False).update(
        is_studies=False,
    )
