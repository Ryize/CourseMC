import re

from django.db import migrations


HELPFUL_MATERIALS_LIST_CLASS = 'lesson-helpful-materials-list'
NUMBERED_MATERIAL_PARAGRAPHS_PATTERN = re.compile(
    r'(?P<label><p(?:\s[^>]*)?>\s*(?:<strong>)?\s*Полезные материалы:'
    r'\s*(?:</strong>)?\s*</p>)'
    r'(?P<items>(?:\s*<p(?:\s[^>]*)?>\s*\d+\)\s*'
    r'(?:&nbsp;|\s)*(?:(?!</p>).)*</p>)+)',
    flags=re.IGNORECASE | re.DOTALL,
)
NUMBERED_MATERIAL_PARAGRAPH_PATTERN = re.compile(
    r'<p(?:\s[^>]*)?>\s*\d+\)\s*(?:&nbsp;|\s)*'
    r'(?P<content>.*?)</p>',
    flags=re.DOTALL,
)


def _number_materials(match):
    items = [
        item.group('content').strip()
        for item in NUMBERED_MATERIAL_PARAGRAPH_PATTERN.finditer(match.group('items'))
    ]
    list_items = ''.join(f'<li>{item}</li>' for item in items)
    return (
        f'{match.group("label")}\n'
        f'<ol class="{HELPFUL_MATERIALS_LIST_CLASS}">{list_items}</ol>'
    )


def number_helpful_materials(apps, schema_editor):
    Schedule = apps.get_model('Course', 'Schedule')

    for schedule in Schedule.objects.filter(
        lesson_materials__icontains='Полезные материалы:',
    ):
        materials = NUMBERED_MATERIAL_PARAGRAPHS_PATTERN.sub(
            _number_materials,
            schedule.lesson_materials,
        )
        if materials != schedule.lesson_materials:
            schedule.lesson_materials = materials.strip()
            schedule.save(update_fields=('lesson_materials',))


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0012_normalize_helpful_materials_markup'),
    ]

    operations = [
        migrations.RunPython(
            number_helpful_materials,
            migrations.RunPython.noop,
        ),
    ]
