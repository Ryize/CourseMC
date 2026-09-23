import json
from pathlib import PurePath

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from Course.models import LessonSolutionFile


MAX_SOURCE_BYTES = 1024 * 1024
MAX_EDITOR_CHARACTERS = 20000
TEXT_EXTENSIONS = {'.py', '.txt', '.md'}


@require_GET
def py_interpreter(request):
    return render(request, 'py_interpreter/py_interpreter.html')


@login_required
@require_GET
@never_cache
def solution_file_in_interpreter(request, file_id):
    """Открыть приватный файл решения в редакторе для его преподавателя."""
    solution_file = get_object_or_404(
        LessonSolutionFile.objects.select_related(
            'solution__student__user',
            'solution__student__groups__teacher',
        ),
        pk=file_id,
    )
    if not request.user.is_superuser and (
        not request.user.is_staff
        or solution_file.solution.student.groups.teacher.user_id != request.user.pk
    ):
        raise PermissionDenied('Этот файл решения недоступен.')

    filename = solution_file.original_name.replace('\\', '/').split('/')[-1]
    extension = PurePath(filename).suffix.lower()
    source_error = ''
    source_code = ''

    if extension not in TEXT_EXTENSIONS | {'.ipynb'}:
        source_error = 'Этот формат нельзя открыть как Python-код. Просмотрите исходный файл или скачайте его.'
    elif solution_file.file.size > MAX_SOURCE_BYTES:
        source_error = 'Файл слишком велик для редактора. Скачайте его, чтобы просмотреть полностью.'
    else:
        try:
            with solution_file.file.open('rb') as source_file:
                content = source_file.read(MAX_SOURCE_BYTES + 1)
            if len(content) > MAX_SOURCE_BYTES:
                source_error = 'Файл слишком велик для редактора. Скачайте его, чтобы просмотреть полностью.'
            else:
                source_code = content.decode('utf-8-sig')
                if extension == '.ipynb':
                    notebook = json.loads(source_code)
                    cells = notebook.get('cells', [])
                    source_code = '\n\n'.join(
                        ''.join(cell.get('source', []))
                        if isinstance(cell.get('source', []), list)
                        else cell.get('source', '')
                        for cell in cells
                        if isinstance(cell, dict) and cell.get('cell_type') == 'code'
                    )
                    if not source_code.strip():
                        source_error = 'В ноутбуке нет ячеек с Python-кодом.'
                if len(source_code) > MAX_EDITOR_CHARACTERS:
                    source_error = 'Код превышает лимит редактора в 20 000 символов. Скачайте файл, чтобы просмотреть полностью.'
        except FileNotFoundError as exc:
            raise Http404('Файл решения не найден.') from exc
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
            source_error = 'Не удалось прочитать код в UTF-8. Просмотрите исходный файл или скачайте его.'

    if source_error:
        source_code = ''
    download_name = filename if extension == '.py' else f'{PurePath(filename).stem}.py'
    return render(
        request,
        'py_interpreter/py_interpreter.html',
        {
            'solution_file': solution_file,
            'source_filename': filename,
            'source_code': source_code,
            'source_error': source_error,
            'download_name': download_name,
            'source_preview_url': f"{reverse('lesson_solution_file_download', args=(file_id,))}?view=1",
            'source_download_url': reverse('lesson_solution_file_download', args=(file_id,)),
        },
    )
