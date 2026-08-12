import re

from django.db import migrations


ASSIGNMENT_LABEL = '<p class="lesson-assignment-label">Задание:</p>'


HELPFUL_MATERIALS = {
    4: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://ru.w3docs.com/learn-python/python-if-else" target="_blank" rel="noopener noreferrer">Условия <code>if</code>, <code>elif</code> и <code>else</code> с примерами</a></li>
            <li><a href="https://youtu.be/dw9q05LZK-w" target="_blank" rel="noopener noreferrer">Разбор предыдущих заданий</a></li>
        </ol>
    ''',
    8: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://ru.w3docs.com/learn-python/python-if-else" target="_blank" rel="noopener noreferrer">Условия и тернарное выражение в Python</a></li>
        </ol>
    ''',
    23: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://education.yandex.ru/handbook/python/article/spisochnye-vyrazheniya-model-pamyati-dlya-tipov-yazyka-python" target="_blank" rel="noopener noreferrer">Списковые выражения: синтаксис и примеры</a></li>
        </ol>
    ''',
    30: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://youtu.be/VATd_GiSniQ" target="_blank" rel="noopener noreferrer">Разбор темы: работа с файлами</a></li>
            <li><a href="https://pythonru.com/osnovy/fajly-v-python-vvod-vyvod" target="_blank" rel="noopener noreferrer">Файлы в Python: чтение и запись</a></li>
            <li><a href="https://tproger.ru/articles/files-in-python/" target="_blank" rel="noopener noreferrer">Работа с файлами на практике</a></li>
        </ol>
    ''',
    33: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://habr.com/ru/articles/308484/" target="_blank" rel="noopener noreferrer">Статическая и динамическая типизация</a></li>
        </ol>
    ''',
    40: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://youtu.be/4cd3yJUZfys" target="_blank" rel="noopener noreferrer">Разбор темы: исключения в Python</a></li>
            <li><a href="https://pythonchik.ru/osnovy/python-try-except" target="_blank" rel="noopener noreferrer">Обработка исключений через <code>try</code>/<code>except</code></a></li>
        </ol>
    ''',
    41: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://pythonworld.ru/tipy-dannyx-v-python/vse-o-funkciyax-i-ix-argumentax.html" target="_blank" rel="noopener noreferrer">Функции и их аргументы</a></li>
            <li><a href="https://pythonru.com/osnovy/funkcii-v-python" target="_blank" rel="noopener noreferrer">Функции в Python: понятное введение</a></li>
        </ol>
    ''',
    51: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://youtu.be/eeGZU4GapPU" target="_blank" rel="noopener noreferrer">Разбор темы: рекурсия</a></li>
            <li><a href="https://foxford.ru/wiki/informatika/rekursiya-v-python" target="_blank" rel="noopener noreferrer">Рекурсия в Python с примерами</a></li>
        </ol>
    ''',
    57: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://zaochnik.ru/blog/kak-sostavit-plan-uchebnogo-proekta-instruktsiya-dlya-shkolnikov-i-studentov-primery/" target="_blank" rel="noopener noreferrer">Как составить план учебного проекта</a></li>
        </ol>
    ''',
    58: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://youtu.be/XMLEKcuVpvg" target="_blank" rel="noopener noreferrer">Разбор темы: классы и объекты</a></li>
            <li><a href="https://itproger.com/course/python/17" target="_blank" rel="noopener noreferrer">Классы и объекты в Python</a></li>
        </ol>
    ''',
    59: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://youtu.be/e6F2xz2M4jQ" target="_blank" rel="noopener noreferrer">Разбор темы: инициализация объектов</a></li>
            <li><a href="https://itproger.com/course/python/17" target="_blank" rel="noopener noreferrer">Конструктор <code>__init__</code> и поля объекта</a></li>
        </ol>
    ''',
    60: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://youtu.be/OAkvFxh2Zds" target="_blank" rel="noopener noreferrer">Разбор темы: наследование и инкапсуляция</a></li>
            <li><a href="https://www.youtube.com/watch?v=M58eiYbM6AE" target="_blank" rel="noopener noreferrer">Видео о наследовании в ООП</a></li>
        </ol>
    ''',
    61: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://youtu.be/jZlFMNAHWfs" target="_blank" rel="noopener noreferrer">Разбор темы: полиморфизм</a></li>
            <li><a href="https://www.youtube.com/watch?v=Ay_GwOQWPs8&amp;t=7s" target="_blank" rel="noopener noreferrer">Видео о полиморфизме</a></li>
        </ol>
    ''',
    62: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://youtu.be/sNERjeZ2VWE" target="_blank" rel="noopener noreferrer">Разбор темы: свойства и валидация</a></li>
            <li><a href="https://habr.com/ru/articles/186608/" target="_blank" rel="noopener noreferrer">Специальные методы и свойства объектов</a></li>
        </ol>
    ''',
    65: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://docs-python.ru/tutorial/oop-python-primerakh/podkhody-oop/" target="_blank" rel="noopener noreferrer">Наследование или композиция: как выбрать подход</a></li>
            <li><a href="/media/uploads/2024/09/18/abstract.py" target="_blank" rel="noopener noreferrer">Пример кода и теория по абстракции</a></li>
        </ol>
    ''',
    68: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://www.youtube.com/watch?v=2qqEGh_1hi8&amp;t=565s" target="_blank" rel="noopener noreferrer">Видео о модульном тестировании</a></li>
            <li><a href="https://habr.com/ru/companies/otus/articles/481806/" target="_blank" rel="noopener noreferrer">Введение в <code>unittest</code></a></li>
            <li><a href="/media/uploads/2024/09/08/test_main.py" target="_blank" rel="noopener noreferrer">Пример файла с тестами</a></li>
        </ol>
    ''',
    74: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://habr.com/ru/articles/354046/" target="_blank" rel="noopener noreferrer">Абстракция, агрегация и композиция</a></li>
            <li><a href="/media/uploads/2024/09/18/abstract.py" target="_blank" rel="noopener noreferrer">Пример кода и теория по абстракции</a></li>
        </ol>
    ''',
    75: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://www.oracle.com/ru/database/what-is-database/" target="_blank" rel="noopener noreferrer">Что такое база данных и какими они бывают</a></li>
            <li><a href="https://russianblogs.com/article/73441278572/" target="_blank" rel="noopener noreferrer">Базовые SQL-запросы</a></li>
        </ol>
    ''',
    76: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://bestprogrammer.ru/izuchenie/chto-takoe-crud-operatsii" target="_blank" rel="noopener noreferrer">CRUD-операции простыми словами</a></li>
        </ol>
    ''',
    77: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://habr.com/ru/post/488054/" target="_blank" rel="noopener noreferrer">Связи между таблицами</a></li>
            <li><a href="https://tproger.ru/articles/indeksy-v-postgresql/" target="_blank" rel="noopener noreferrer">Что такое индексы в базе данных</a></li>
        </ol>
    ''',
    78: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://tproger.ru/translations/sql-recap/" target="_blank" rel="noopener noreferrer">Краткое повторение основных SQL-запросов</a></li>
        </ol>
    ''',
    80: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://pytba.readthedocs.io/ru/latest/quick_start.html" target="_blank" rel="noopener noreferrer">Быстрый старт PyTelegramBotAPI</a></li>
        </ol>
    ''',
    116: '''
        <p>Полезные материалы:</p>
        <ol>
            <li><a href="https://flask.palletsprojects.com/en/stable/quickstart/" target="_blank" rel="noopener noreferrer">Flask: быстрый старт и структура приложения</a></li>
        </ol>
    ''',
}


SHORT_PIP_MEMO = re.compile(
    r'\s*<li>\s*<strong>Короткая памятка:</strong>\s*'
    r'устанавливайте пакеты командой\s*'
    r'<code>python -m pip install имя-пакета</code>;\s*'
    r'список пакетов проекта сохраняют в\s*'
    r'<code>requirements\.txt</code>\.\s*</li>',
    flags=re.DOTALL,
)
UNNECESSARY_STAIRS_NOTE = re.compile(
    r'\s*Динамическое программирование и подсчёт вариантов не нужны\.',
)


def _add_materials(materials, helpful_materials):
    if 'Полезные материалы:' in materials:
        return materials
    label_index = materials.find(ASSIGNMENT_LABEL)
    if label_index == -1:
        return f'{helpful_materials.strip()}\n{materials.strip()}'.strip()
    return (
        f'{materials[:label_index]}{helpful_materials.strip()}\n'
        f'{materials[label_index:]}'
    ).strip()


def restore_helpful_lesson_materials(apps, schema_editor):
    DirectionStudy = apps.get_model('Course', 'DirectionStudy')
    Schedule = apps.get_model('Course', 'Schedule')
    backend_direction = DirectionStudy.objects.filter(title='Backend 2024').first()
    if not backend_direction:
        return

    schedules = Schedule.objects.filter(
        direction_id=backend_direction.pk,
        position__in=(*HELPFUL_MATERIALS, 28, 50),
    )
    for schedule in schedules:
        materials = schedule.lesson_materials or ''

        if schedule.position == 28:
            materials = SHORT_PIP_MEMO.sub('', materials)
        if schedule.position == 50:
            materials = UNNECESSARY_STAIRS_NOTE.sub('', materials)
        if schedule.position == 57:
            materials = (
                f'{ASSIGNMENT_LABEL}'
                '<p class="lesson-assignment-text">'
                'Задание будет выдано преподавателем.</p>'
            )
        if schedule.position in (33, 80):
            materials = HELPFUL_MATERIALS[schedule.position].strip()
        elif schedule.position in HELPFUL_MATERIALS:
            materials = _add_materials(
                materials,
                HELPFUL_MATERIALS[schedule.position],
            )

        if materials != schedule.lesson_materials:
            schedule.lesson_materials = materials
            schedule.save(update_fields=('lesson_materials',))


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0010_refine_assignment_text'),
    ]

    operations = [
        migrations.RunPython(
            restore_helpful_lesson_materials,
            migrations.RunPython.noop,
        ),
    ]
