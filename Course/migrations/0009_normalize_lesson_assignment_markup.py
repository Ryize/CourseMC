import re

from django.db import migrations


ASSIGNMENT_LABEL = '<p class="lesson-assignment-label">Задание:</p>'
ASSIGNMENT_LIST_CLASS = 'lesson-assignment-list'


STRONG_ASSIGNMENT_PATTERN = re.compile(
    r'<p(?P<attributes>\s[^>]*)?>\s*'
    r'<strong>\s*Задани(?:е|я)\s*:\s*(?:&nbsp;|\s)*</strong>'
    r'(?P<content>.*?)</p>',
    flags=re.IGNORECASE | re.DOTALL,
)
PLAIN_ASSIGNMENT_PATTERN = re.compile(
    r'<p(?P<attributes>\s[^>]*)?>\s*'
    r'Задани(?:е|я)\s*:\s*(?:&nbsp;|\s)*(?P<content>.*?)</p>',
    flags=re.IGNORECASE | re.DOTALL,
)
NUMBERED_PARAGRAPHS_PATTERN = re.compile(
    r'(?P<label><p class="lesson-assignment-label">Задание:</p>)'
    r'(?P<items>(?:\s*<p(?:\s[^>]*)?>\s*\d+\)\s*'
    r'(?:&nbsp;|\s)*(?:(?!</p>).)*</p>){2,})',
    flags=re.DOTALL,
)
NUMBERED_PARAGRAPH_PATTERN = re.compile(
    r'<p(?:\s[^>]*)?>\s*\d+\)\s*(?:&nbsp;|\s)*'
    r'(?P<content>.*?)</p>',
    flags=re.DOTALL,
)
ORDERED_LIST_AFTER_LABEL_PATTERN = re.compile(
    r'(?P<label><p class="lesson-assignment-label">Задание:</p>\s*)'
    r'<ol(?P<attributes>\s[^>]*)?>',
    flags=re.DOTALL,
)
UNORDERED_LIST_AFTER_LABEL_PATTERN = re.compile(
    r'(?P<label><p class="lesson-assignment-label">Задание:</p>\s*)'
    r'<ul(?P<attributes>\s[^>]*)?>(?P<content>.*?)</ul>',
    flags=re.DOTALL,
)
CSS_CLASS_PATTERN = re.compile(r'\sclass=(?P<quote>["\'])(?P<value>.*?)(?P=quote)')


def _is_empty_html(value):
    return not value.replace('&nbsp;', '').replace('\xa0', '').strip()


def _assignment_label_with_content(match):
    content = match.group('content').strip()
    if _is_empty_html(content):
        return ASSIGNMENT_LABEL
    return f'{ASSIGNMENT_LABEL}<p class="lesson-assignment-text">{content}</p>'


def _assignment_list_opening(tag, attributes):
    attributes = attributes or ''
    css_class = CSS_CLASS_PATTERN.search(attributes)
    if css_class:
        classes = css_class.group('value').split()
        if ASSIGNMENT_LIST_CLASS not in classes:
            classes.append(ASSIGNMENT_LIST_CLASS)
        attributes = (
            attributes[:css_class.start()]
            + f' class="{" ".join(classes)}"'
            + attributes[css_class.end():]
        )
    else:
        attributes = f' class="{ASSIGNMENT_LIST_CLASS}"{attributes}'
    return f'<{tag}{attributes}>'


def _replace_numbered_paragraphs(match):
    items = [
        item.group('content').strip()
        for item in NUMBERED_PARAGRAPH_PATTERN.finditer(match.group('items'))
    ]
    list_items = ''.join(f'<li>{item}</li>' for item in items)
    return f'{match.group("label")}<ol class="{ASSIGNMENT_LIST_CLASS}">{list_items}</ol>'


def _replace_ordered_list(match):
    return (
        f'{match.group("label")}'
        f'{_assignment_list_opening("ol", match.group("attributes"))}'
    )


def _replace_unordered_list(match):
    return (
        f'{match.group("label")}'
        f'{_assignment_list_opening("ol", match.group("attributes"))}'
        f'{match.group("content")}</ol>'
    )


def _replace_assignment_tail(materials, assignment_html):
    label = materials.find(ASSIGNMENT_LABEL)
    if label == -1:
        return materials
    return f'{materials[:label]}{assignment_html}'


BACKEND_2024_ASSIGNMENT_TAILS = {
    2: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Запросите число <code>x</code>,
        вычислите выражение <code>x² + 48x − 19</code> и выведите результат.
        Задание разбирается в видео.</p>
    ''',
    28: '''
        <p class="lesson-assignment-label">Задание:</p>
        <p class="lesson-assignment-text">Пользователь задаёт границы
        диапазона. Программа выводит по одному числу в секунду и показывает,
        сколько секунд уже прошло.</p>
    ''',
    29: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Программа загадывает число согласно выбранному уровню
                сложности.</li>
            <li>Добавьте уровни: от 0 до 10, от 0 до 25, от 0 до 50 и от 0
                до 100.</li>
            <li>После попытки сообщайте, угадано ли число.</li>
            <li>Продолжайте игру до правильного ответа и посчитайте попытки.</li>
            <li>Если попыток меньше трёх, выведите «Удача на твоей стороне!»,
                иначе покажите количество попыток. Добавьте подсказку
                «больше» или «меньше».</li>
        </ol>
    ''',
    47: '''
        <p class="lesson-assignment-label">Задание:</p>
        <ol class="lesson-assignment-list">
            <li>Напишите функцию, которая принимает строку и подсчитывает
                количество букв верхнего и нижнего регистра. Для строки
                «Быстрая Лиса Бровей» ожидаемый результат: 3 заглавные и 14
                строчных букв.</li>
            <li>Напишите функцию, которая возвращает новый список с
                уникальными элементами исходного списка.</li>
        </ol>
    ''',
}


def normalize_assignment_markup(apps, schema_editor):
    DirectionStudy = apps.get_model('Course', 'DirectionStudy')
    Schedule = apps.get_model('Course', 'Schedule')
    backend_direction = DirectionStudy.objects.filter(title='Backend 2024').first()

    for schedule in Schedule.objects.exclude(lesson_materials__isnull=True):
        materials = schedule.lesson_materials
        if 'Задани' not in materials:
            continue

        materials = STRONG_ASSIGNMENT_PATTERN.sub(
            _assignment_label_with_content,
            materials,
        )
        materials = PLAIN_ASSIGNMENT_PATTERN.sub(
            _assignment_label_with_content,
            materials,
        )

        if backend_direction and schedule.direction_id == backend_direction.pk:
            assignment_tail = BACKEND_2024_ASSIGNMENT_TAILS.get(schedule.position)
            if assignment_tail:
                materials = _replace_assignment_tail(
                    materials,
                    assignment_tail.strip(),
                )

        materials = NUMBERED_PARAGRAPHS_PATTERN.sub(
            _replace_numbered_paragraphs,
            materials,
        )
        materials = UNORDERED_LIST_AFTER_LABEL_PATTERN.sub(
            _replace_unordered_list,
            materials,
        )
        materials = ORDERED_LIST_AFTER_LABEL_PATTERN.sub(
            _replace_ordered_list,
            materials,
        )

        if materials != schedule.lesson_materials:
            schedule.lesson_materials = materials.strip()
            schedule.save(update_fields=('lesson_materials',))


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0008_update_backend_2024_curriculum'),
    ]

    operations = [
        migrations.RunPython(
            normalize_assignment_markup,
            migrations.RunPython.noop,
        ),
    ]
