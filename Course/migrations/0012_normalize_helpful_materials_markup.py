import re

from django.db import migrations


HELPFUL_MATERIALS_LIST_CLASS = 'lesson-helpful-materials-list'
HELPFUL_LINKS_SECTION_PATTERN = re.compile(
    r'\s*<p(?:\s[^>]*)?>\s*(?:<strong>)?\s*Полезные ссылки:\s*'
    r'(?:</strong>)?\s*</p>\s*<ol(?:\s[^>]*)?>.*?</ol>',
    flags=re.IGNORECASE | re.DOTALL,
)
HELPFUL_MATERIALS_LIST_PATTERN = re.compile(
    r'(?P<label><p(?:\s[^>]*)?>\s*(?:<strong>)?\s*Полезные материалы:'
    r'\s*(?:</strong>)?\s*</p>\s*)'
    r'<ol(?P<attributes>\s[^>]*)?>',
    flags=re.IGNORECASE | re.DOTALL,
)
CSS_CLASS_PATTERN = re.compile(r'\sclass=(?P<quote>["\'])(?P<value>.*?)(?P=quote)')


def _list_opening(attributes):
    attributes = attributes or ''
    css_class = CSS_CLASS_PATTERN.search(attributes)
    if css_class:
        classes = css_class.group('value').split()
        if HELPFUL_MATERIALS_LIST_CLASS not in classes:
            classes.append(HELPFUL_MATERIALS_LIST_CLASS)
        attributes = (
            attributes[:css_class.start()]
            + f' class="{" ".join(classes)}"'
            + attributes[css_class.end():]
        )
    else:
        attributes = f' class="{HELPFUL_MATERIALS_LIST_CLASS}"{attributes}'
    return f'<ol{attributes}>'


def _normalize_helpful_materials_list(match):
    return f'{match.group("label")}{_list_opening(match.group("attributes"))}'


def normalize_helpful_materials_markup(apps, schema_editor):
    Schedule = apps.get_model('Course', 'Schedule')

    for schedule in Schedule.objects.exclude(lesson_materials__isnull=True):
        materials = schedule.lesson_materials
        materials = HELPFUL_LINKS_SECTION_PATTERN.sub('', materials)
        materials = HELPFUL_MATERIALS_LIST_PATTERN.sub(
            _normalize_helpful_materials_list,
            materials,
        )

        if materials != schedule.lesson_materials:
            schedule.lesson_materials = materials.strip()
            schedule.save(update_fields=('lesson_materials',))


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0011_restore_helpful_lesson_materials'),
    ]

    operations = [
        migrations.RunPython(
            normalize_helpful_materials_markup,
            migrations.RunPython.noop,
        ),
    ]
