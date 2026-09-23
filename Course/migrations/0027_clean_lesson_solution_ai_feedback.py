"""Убирает имена файлов из уже подготовленных ИИ-замечаний."""

import re

from django.db import migrations


OLD_INTRO = 'По предварительной проверке есть замечания:\n'
FILE_PREFIX = re.compile(
    r'(?m)^(\d+\.\s+)(?:[^:\r\n]{1,120}\.(?:py|ipynb|txt|md|docx)|Файл решения):[ \t]*',
    flags=re.IGNORECASE,
)


def normalize_newlines(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


def clean_feedback(text):
    normalized = normalize_newlines(text)
    if not normalized.startswith(OLD_INTRO):
        return text
    return FILE_PREFIX.sub(r'\1', normalized[len(OLD_INTRO):])


def clean_existing_ai_feedback(apps, schema_editor):
    Submission = apps.get_model('Course', 'LessonSolutionSubmission')
    Solution = apps.get_model('Course', 'LessonSolution')

    for submission in Submission.objects.exclude(ai_feedback='').select_related(
        'solution',
    ).iterator(chunk_size=200):
        old_feedback = submission.ai_feedback
        new_feedback = clean_feedback(old_feedback)
        if new_feedback == old_feedback:
            continue

        old_comment = submission.solution.teacher_comment
        if normalize_newlines(old_comment) == normalize_newlines(old_feedback):
            newline = '\r\n' if '\r\n' in old_comment else '\n'
            Solution.objects.filter(
                pk=submission.solution_id,
                teacher_comment=old_comment,
            ).update(teacher_comment=new_feedback.replace('\n', newline))
        Submission.objects.filter(pk=submission.pk).update(ai_feedback=new_feedback)


class Migration(migrations.Migration):
    dependencies = [
        ('Course', '0026_lessonsolutionsubmission_ai_review'),
    ]

    operations = [
        migrations.RunPython(clean_existing_ai_feedback, migrations.RunPython.noop),
    ]
