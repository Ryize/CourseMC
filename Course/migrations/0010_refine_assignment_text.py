import re

from django.db import migrations


ASSIGNMENT_TEXT_START_PATTERN = re.compile(
    r'(<p class="lesson-assignment-text">\s*)([а-яё])',
)
ASSIGNMENT_LIST_PATTERN = re.compile(
    r'(?P<open><ol class="lesson-assignment-list">)'
    r'(?P<content>.*?)'
    r'(?P<close></ol>)',
    flags=re.DOTALL,
)
LIST_ITEM_START_PATTERN = re.compile(r'(<li(?:\s[^>]*)?>\s*)([а-яё])')
OUTDATED_BANK_ACCOUNT_NOTE = re.compile(
    r'\s*Некорректная сумма и недостаточный баланс.*?'
    r'собственные исключения добавим позже\.',
    flags=re.DOTALL,
)


def _capitalize(match):
    return f'{match.group(1)}{match.group(2).upper()}'


def _capitalize_list_items(match):
    content = LIST_ITEM_START_PATTERN.sub(_capitalize, match.group('content'))
    return f'{match.group("open")}{content}{match.group("close")}'


def refine_assignment_text(apps, schema_editor):
    DirectionStudy = apps.get_model('Course', 'DirectionStudy')
    Schedule = apps.get_model('Course', 'Schedule')
    backend_direction = DirectionStudy.objects.filter(title='Backend 2024').first()

    for schedule in Schedule.objects.filter(
        lesson_materials__icontains='lesson-assignment-label',
    ):
        materials = ASSIGNMENT_TEXT_START_PATTERN.sub(
            _capitalize,
            schedule.lesson_materials,
        )
        materials = ASSIGNMENT_LIST_PATTERN.sub(
            _capitalize_list_items,
            materials,
        )

        if (
            backend_direction
            and schedule.direction_id == backend_direction.pk
            and schedule.position == 67
        ):
            materials = OUTDATED_BANK_ACCOUNT_NOTE.sub(
                ' Не допускайте некорректные суммы и снятие средств сверх баланса.',
                materials,
            )

        if materials != schedule.lesson_materials:
            schedule.lesson_materials = materials
            schedule.save(update_fields=('lesson_materials',))


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0009_normalize_lesson_assignment_markup'),
    ]

    operations = [
        migrations.RunPython(
            refine_assignment_text,
            migrations.RunPython.noop,
        ),
    ]
