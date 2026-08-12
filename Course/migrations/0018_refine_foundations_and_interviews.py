import re

from django.db import migrations
from django.utils import timezone


PLANS = {
    1: 'Установка Python и PyCharm, создание проекта, первый запуск программы, ввод и вывод данных.',
    2: 'Числа, строки, переменные, преобразование типов и базовые арифметические операции.',
    3: 'Логические выражения, конструкция if/elif/else и выбор ветви выполнения программы.',
    4: 'Операторы and, or и not, вложенные условия и чтение составных логических выражений.',
    5: 'Сравнение двух и трёх чисел, поиск среднего значения и разбор граничных случаев.',
    6: 'Классификация числа по знаку, чётности и особым значениям с помощью условий.',
    7: 'Объединение нескольких признаков в одном условии и упрощение сложных проверок.',
    8: 'Основные методы строк, нормализация пользовательского ввода и тернарный оператор.',
    9: 'Проверка принадлежности диапазону, работа со временем и непересекающимися условиями.',
    10: 'Сезоны, календарные условия, правило високосного года и итоговое закрепление условий.',
    11: 'Циклы for и while, счётчик, условие продолжения и выбор подходящего вида цикла.',
    12: 'Вложенные циклы, накопление результата, break и continue в повторяющихся действиях.',
    13: 'Создание списков, индексы, срезы, основные методы и перебор элементов.',
    14: 'Практика while: изменение счётчика, обратный отсчёт и защита от бесконечного цикла.',
    15: 'Практика for и range: границы, шаг, повторение действий и сравнение с while.',
    16: 'Решение числовых задач с помощью while: цифры числа, факториал и накопление результата.',
    17: 'Алгоритмические задачи с циклами, числовые последовательности и проверка результата.',
    18: 'Использование списка как простого каталога: просмотр, добавление, изменение и удаление записей.',
    19: 'Создание словарей, ключи и значения, методы get, update, keys, values и items.',
    20: 'Практика словарей: поиск, обновление, подсчёт частот и хранение составных записей.',
    21: 'Циклы в задачах на проценты, изменение величины по шагам и моделирование роста.',
    22: 'Повторное решение знакомых числовых задач с помощью for и сравнение двух видов циклов.',
    23: 'Множества и кортежи, уникальность значений, операции над множествами и неизменяемость.',
    24: 'Списковые включения, преобразование и фильтрация элементов с одним понятным выражением.',
    25: 'Построение текстовых шаблонов с помощью циклов и управление направлением вывода.',
    26: 'Регистр символов, проверка принадлежности символа и фильтрация строк.',
    27: 'Функции ord и chr, таблица Unicode и подсчёт числовых характеристик строки.',
    28: 'Стандартные модули, внешние пакеты, pip, виртуальное окружение и фиксация зависимостей.',
    29: 'Использование random в первой линейной версии игры и организация игрового цикла.',
    30: 'Открытие и закрытие файла, режимы чтения, проход по строкам и подсчёт данных.',
    31: 'Чтение строк из файла, нормализация текста и проверка слов на палиндром.',
    32: 'Поиск данных в файле, накопление статистики и обработка пустого результата.',
    33: 'Компиляция и интерпретация, путь кода в CPython, байт-код и динамическая типизация.',
    34: 'Разделение строк файла на слова, очистка текста и вычисление характеристик слов.',
    35: 'Преобразование строк при чтении файла и запись обработанного результата.',
    36: 'Подсчёт букв, цифр и специальных символов в содержимом файла.',
    37: 'Чтение числовых данных из файла, преобразование типов и вычисление результата.',
    38: 'Делители числа, сумма цифр, критерий выбора лучшего результата и разбор равных вариантов.',
    39: 'Обработка массива: положительные элементы, поиск экстремумов и диапазон между ними.',
    40: 'Исключения, try/except/else/finally, ожидаемые ошибки и понятные сообщения пользователю.',
    41: 'Декомпозиция задачи, объявление и вызов функции, параметры и возвращаемое значение.',
    42: 'Разделение файловой задачи на функции и передача ошибок на подходящий уровень программы.',
    43: 'Имена, отступы, длина строк, структура модуля и практическое применение PEP 8.',
    44: 'Функции для обработки строк, разбиение задачи на шаги и повторное использование кода.',
    45: 'Закрепление функций на знакомых задачах, работа с диапазонами и представление даты кортежем.',
    46: 'Аннотации параметров и результата, точка входа программы и проверка простого числа.',
    47: 'Передача коллекций в функции, удаление повторов и преобразование регистра.',
    48: 'Функции-предикаты, булев результат и объединение небольших проверок.',
    49: 'Рефакторинг игры «Угадай число»: отдельные функции, единая ответственность и игровой цикл.',
    50: 'Функция построения лесенки, параметры размера и символа, проверка входных данных.',
    51: 'Рекурсивный вызов, базовый случай, движение к завершению и сравнение с циклом.',
    52: 'Постановка задачи «Пирамида», уточнение требований и проектирование первого решения.',
    53: 'Продолжение задачи «Пирамида», разбор промежуточного результата и исправление алгоритма.',
    54: 'Завершение задачи «Пирамида», обработка граничных случаев и улучшение читаемости кода.',
    55: 'Функции как объекты, функция-обёртка, замыкание и применение собственного декоратора.',
    56: 'Повторение функций, параметров, коллекций, рекурсии и алгоритмических приёмов.',
    57: 'Подготовка итоговой работы: требования, декомпозиция, структура и критерии готовности.',
    58: 'Класс как описание объекта, создание экземпляра, атрибуты и методы экземпляра.',
    59: 'Метод __init__, начальное состояние объекта и изменение состояния через методы.',
    60: 'Наследование, расширение родительского класса и управление доступом к состоянию.',
    61: 'Единый интерфейс разных классов, переопределение методов и полиморфное поведение.',
    62: 'Свойства, getter и setter, проверка значений и защита корректного состояния объекта.',
    63: 'Специальные методы Python и понятное строковое представление пользовательского объекта.',
    64: 'Перенос предметной области в классы, связи объектов и распределение ответственности.',
    65: 'Абстрактные классы, композиция объектов и выбор отношения между сущностями.',
    66: 'Проектирование нескольких взаимодействующих классов по требованиям и сценариям.',
    67: 'Модель банковского счёта, операции, ограничения и сохранение истории изменений.',
    68: 'Структура unittest, тестовый случай, подготовка данных и основные проверки.',
    69: 'Позитивные, негативные и граничные сценарии для методов и функций.',
    70: 'Закрепление unittest, независимость тестов и поиск причины падения проверки.',
    71: 'Тестирование алгоритмических задач, наборы входных данных и ожидаемые результаты.',
    72: 'Собственные исключения предметной области и проверка ошибочных операций в тестах.',
    73: 'UML-диаграмма классов: атрибуты, методы, наследование, композиция и зависимости.',
    74: 'Финальная архитектурная доработка, устранение повторов, проверка интерфейсов и тестов.',
    75: 'Реляционная модель, таблицы, строки, столбцы, первичные ключи и проектирование схемы.',
    76: 'SQL-команды INSERT, SELECT, UPDATE и DELETE и безопасное изменение данных.',
    77: 'Связи таблиц, внешние ключи, JOIN, ограничения и назначение индексов.',
    78: 'GROUP BY, агрегатные функции, HAVING и получение итоговых показателей из данных.',
}


YANDEX_PYTHON = (
    'Яндекс Хендбук: что такое Python',
    'https://education.yandex.ru/handbook/python/article/chto-takoe-python',
)
PYTHON_FAQ = (
    'Python FAQ: что такое Python',
    'https://docs.python.org/3/faq/general.html#what-is-python',
)
YANDEX_MEMORY = (
    'Яндекс Хендбук: типы и модель памяти',
    'https://education.yandex.ru/handbook/python/article/spisochnye-vyrazheniya-model-pamyati-dlya-tipov-yazyka-python',
)
YANDEX_TUPLES = (
    'Яндекс Хендбук: строки, кортежи и списки',
    'https://education.yandex.ru/handbook/python/article/stroki-kortezhi-spiski',
)
YANDEX_SETS_DICTS = (
    'Яндекс Хендбук: множества и словари',
    'https://education.yandex.ru/handbook/python/article/mnozhestva-slovari',
)
VENV = (
    'Python: виртуальные окружения и пакеты',
    'https://docs.python.org/3/tutorial/venv.html',
)


def render_materials(resources=(), assignment=''):
    parts = []
    if resources:
        parts.append('<p>Полезные материалы:</p>')
        parts.append('<ul class="lesson-helpful-materials-list">')
        for label, url in resources:
            parts.append(
                '<li><a href="{}" target="_blank" rel="noopener noreferrer">{}</a></li>'.format(
                    url, label,
                )
            )
        parts.append('</ul>')
    if assignment:
        parts.append('<p class="lesson-assignment-label">Задание:</p>')
        if isinstance(assignment, (tuple, list)):
            parts.append('<ol class="lesson-assignment-list">')
            parts.extend('<li>{}</li>'.format(item) for item in assignment)
            parts.append('</ol>')
        else:
            parts.append('<p class="lesson-assignment-text">{}</p>'.format(assignment))
    return ''.join(parts)


def add_quiz_link(materials, quiz, label):
    materials = re.sub(
        r'<p data-quiz-id="\d+">.*?</p>',
        '',
        materials or '',
        flags=re.DOTALL,
    )
    return materials + (
        '<p data-quiz-id="{id}"><strong>Проверь себя:</strong> '
        '<a href="/questionnaire/take_poll/{id}/" target="_blank" '
        'rel="noopener noreferrer">Пройти опрос «{label}»</a></p>'
    ).format(id=quiz.pk, label=label)


def clone_collections_quiz(apps):
    Quiz = apps.get_model('questionnaire', 'Quiz')
    Question = apps.get_model('questionnaire', 'Question')
    AnswerQuestion = apps.get_model('questionnaire', 'AnswerQuestion')

    original = Quiz.objects.filter(pk=10).first()
    if not original:
        return None

    existing = Quiz.objects.filter(
        title='Python: циклы, словари и коллекции',
        is_archived=False,
    ).first()
    if existing:
        return existing

    original.is_archived = True
    original.archived_at = timezone.now()
    original.save(update_fields=('is_archived', 'archived_at'))

    quiz = Quiz.objects.create(
        title='Python: циклы, словари и коллекции',
        description=(
            'Проверяем циклы, списки, словари, множества, кортежи '
            'и списковые включения.'
        ),
        topic=original.topic,
        lifetime=original.lifetime,
        user_id=original.user_id,
    )

    for old_question in Question.objects.filter(quiz_id=original.pk).order_by('pk'):
        question = Question.objects.create(
            quiz_id=quiz.pk,
            question=old_question.question,
        )
        AnswerQuestion.objects.bulk_create([
            AnswerQuestion(
                question_id=question.pk,
                answer=answer.answer,
                correct=answer.correct,
            )
            for answer in AnswerQuestion.objects.filter(
                question_id=old_question.pk,
            ).order_by('pk')
        ])

    additions = (
        (
            'Когда удобнее использовать цикл while?',
            (
                ('Когда число повторений заранее неизвестно', True),
                ('Только для перебора списка', False),
                ('Только когда нужен range', False),
                ('Когда цикл должен выполниться ровно один раз', False),
            ),
        ),
        (
            'Для чего чаще всего используют set?',
            (
                ('Для хранения только строк', False),
                ('Для уникальных элементов и операций над множествами', True),
                ('Для доступа к элементу по индексу', False),
                ('Для хранения пар ключ-значение', False),
            ),
        ),
        (
            'Какое свойство отличает tuple от list?',
            (
                ('Кортеж нельзя изменить после создания', True),
                ('В кортеже могут быть только числа', False),
                ('У кортежа нет порядка элементов', False),
                ('Кортеж всегда содержит уникальные значения', False),
            ),
        ),
    )
    for question_text, answers in additions:
        question = Question.objects.create(
            quiz_id=quiz.pk,
            question=question_text,
        )
        AnswerQuestion.objects.bulk_create([
            AnswerQuestion(
                question_id=question.pk,
                answer=answer,
                correct=correct,
            )
            for answer, correct in answers
        ])
    return quiz


def refine_curriculum(apps, schema_editor):
    DirectionStudy = apps.get_model('Course', 'DirectionStudy')
    Schedule = apps.get_model('Course', 'Schedule')
    Quiz = apps.get_model('questionnaire', 'Quiz')

    direction = DirectionStudy.objects.filter(title='Backend 2024').first()
    if not direction:
        return

    schedules = {
        schedule.position: schedule
        for schedule in Schedule.objects.filter(
            direction_id=direction.pk,
            is_archived=False,
            position__gte=1,
            position__lte=176,
        )
    }
    if set(schedules) != set(range(1, 177)):
        raise RuntimeError('Для обновления программы нужны уроки с 1 по 176 без пропусков.')

    # Сохраняем объекты уроков и прикреплённые к ним решения, меняя только порядок.
    ordered = []
    ordered.extend(schedules[position] for position in range(1, 115))
    ordered.append(schedules[156])
    ordered.extend(schedules[position] for position in range(115, 144))
    ordered.append(schedules[157])
    ordered.extend(schedules[position] for position in range(144, 156))
    ordered.extend(schedules[position] for position in range(159, 177))
    ordered.append(schedules[158])
    for position, schedule in enumerate(ordered, start=1):
        schedule.position = position

    # Планы фундаментальной части.
    for position in range(1, 79):
        schedules[position].plan = '<p>{}</p>'.format(PLANS[position])

    schedules[16].lesson_materials = schedules[16].lesson_materials.replace(
        '<ol class="lesson-assignment-list">',
        '<p class="lesson-assignment-text">Решите все задачи с помощью цикла <code>while</code>. Позже вы вернётесь к части этих условий и сравните решение с циклом <code>for</code>.</p><ol class="lesson-assignment-list">',
        1,
    )

    schedules[19].lesson_materials = render_materials(
        (YANDEX_SETS_DICTS,),
        (
            'Создайте словарь кодов для букв и зашифруйте введённую строку. Символы, которых нет в словаре, оставляйте без изменения. Затем расшифруйте результат обратным словарём.',
            'Подсчитайте, сколько раз каждое слово встречается в тексте. Регистр не должен влиять на подсчёт. Выведите слово с наибольшей частотой.',
        ),
    )
    schedules[20].theme = 'Словари. Поиск и обновление данных'
    schedules[20].lesson_type = 'Практика'
    schedules[20].lesson_materials = render_materials(
        (YANDEX_SETS_DICTS,),
        (
            'Создайте телефонную книгу в виде словаря. Добавьте просмотр, поиск по имени, добавление, изменение и удаление контакта. Обработайте попытку открыть отсутствующий контакт.',
            'Дан список покупок вида «покупатель, товар, количество». Соберите словарь, в котором для каждого покупателя хранится его список товаров и общее количество позиций.',
            'Дан словарь остатков товаров. Примените несколько поставок и продаж, не допуская отрицательного остатка. В конце выведите товары, которые закончились.',
        ),
    )

    schedules[22].lesson_materials = schedules[22].lesson_materials.replace(
        '<ol class="lesson-assignment-list">',
        '<p class="lesson-assignment-text">Решите знакомые задачи заново, но теперь используйте цикл <code>for</code>. После решения сравните его с предыдущей версией на <code>while</code>: где условие завершения и счётчик читаются понятнее?</p><ol class="lesson-assignment-list">',
        1,
    )

    schedules[23].theme = 'Множества и кортежи. Уникальность и неизменяемость'
    schedules[23].lesson_type = 'Новая тема'
    schedules[23].lesson_materials = render_materials(
        (YANDEX_TUPLES, YANDEX_SETS_DICTS),
        (
            'Дан список городов с повторениями. Получите множество уникальных городов и посчитайте, сколько повторяющихся записей было удалено.',
            'Даны множества учеников двух кружков. Выведите тех, кто посещает оба кружка, только первый кружок и хотя бы один из кружков.',
            'Храните координаты точек кортежами <code>(x, y)</code>. Соберите множество точек, удалите повторы и объясните, почему список нельзя использовать как элемент множества.',
        ),
    )

    # В №28 сохраняем прежнюю практику и добавляем отдельную работу с окружением.
    schedules[28].lesson_materials = render_materials(
        (
            ('Python Package Index: каталог пакетов', 'https://pypi.org'),
            VENV,
            ('Python: модуль time', 'https://pythonworld.ru/moduli/modul-time.html'),
        ),
        (
            'Создайте для учебного проекта виртуальное окружение, активируйте его и убедитесь, что команды <code>python</code> и <code>pip</code> относятся именно к этому окружению.',
            'Установите один небольшой внешний пакет, используйте его в программе и сохраните список зависимостей проекта в <code>requirements.txt</code>. Затем создайте новое окружение и восстановите зависимости из файла.',
            'Пользователь задаёт границы диапазона. Программа выводит по одному числу в секунду и показывает, сколько секунд уже прошло.',
        ),
    )

    schedules[29].lesson_materials = schedules[29].lesson_materials.replace(
        '<ol class="lesson-assignment-list">',
        '<p class="lesson-assignment-text">Это первая версия игры: реализуйте её последовательно в одном игровом цикле. В уроке №49 вы вернётесь к этому проекту и разделите код на функции.</p><ol class="lesson-assignment-list">',
        1,
    )

    schedules[33].lesson_materials = render_materials(
        (YANDEX_PYTHON, PYTHON_FAQ, YANDEX_MEMORY),
        (
            'Запустите интерактивный интерпретатор Python, выполните несколько выражений и завершите сеанс.',
            'Присвойте одной переменной сначала число, затем строку. После каждого присваивания выведите значение и результат <code>type()</code>. Своими словами объясните динамическую типизацию.',
            'Создайте небольшой модуль, импортируйте его из другой программы и найдите появившийся каталог <code>__pycache__</code>. Объясните, зачем Python сохраняет байт-код.',
        ),
    )

    schedules[38].theme = 'Алгоритмы. Делители и сумма цифр'
    schedules[39].theme = 'Алгоритмы. Сумма и произведение элементов'

    schedules[45].lesson_materials = schedules[45].lesson_materials.replace(
        '<ol class="lesson-assignment-list">',
        '<p class="lesson-assignment-text">Первые две задачи встречались раньше намеренно. Решите их без просмотра старого кода, затем сравните версии: сигнатуры функций, имена, проверки границ и возвращаемые значения.</p><ol class="lesson-assignment-list">',
        1,
    )
    schedules[49].lesson_materials = schedules[49].lesson_materials.replace(
        '<p class="lesson-assignment-text">Реализуйте игру',
        '<p class="lesson-assignment-text">Вернитесь к игре из урока №29 и переработайте её через функции. Реализуйте игру',
        1,
    )

    # Три возрастающих пробных собеседования после Flask, Django/DRF и FastAPI.
    interview_flask = schedules[156]
    interview_flask.theme = 'Собеседование. Python, SQL и Flask'
    interview_flask.plan = (
        '<p>Первое пробное интервью: рассказ о себе, Python, ООП, тестирование, SQL, HTTP, Flask и защита собственного проекта.</p>'
    )
    interview_flask.lesson_materials = render_materials(
        (
            ('hh.ru: подготовка к собеседованию', 'https://hh.ru/article/interview_practice_guide'),
            ('Вопросы для Python-собеседования', 'https://github.com/yakimka/python_interview_questions'),
        ),
        'Пройдите пробное интервью и защитите Flask-проект. После встречи запишите вопросы, вызвавшие затруднение, и подготовьте исправленные ответы с короткими примерами.',
    )

    interview_django = schedules[157]
    interview_django.theme = 'Собеседование. Django и REST API'
    interview_django.plan = (
        '<p>Второе пробное интервью: повторение первого этапа, Django, ORM, права, Redis, Celery, DRF, API и архитектура ФинТех-проекта.</p>'
    )
    interview_django.lesson_materials = render_materials(
        (
            ('Вопросы для Python-собеседования', 'https://github.com/yakimka/python_interview_questions'),
            ('Карта знаний backend-разработчика', 'https://roadmap.sh/backend'),
        ),
        'Пройдите расширенное техническое интервью и разберите ФинТех-проект: путь запроса, данные, права, транзакции, фоновые задачи и устройство API. Дополните список тем для повторения.',
    )

    interview_fastapi = schedules[158]
    interview_fastapi.theme = 'Собеседование. Backend и FastAPI'
    interview_fastapi.plan = (
        '<p>Итоговое пробное интервью: все предыдущие темы, конкурентность, asyncio, FastAPI, SQLAlchemy, PostgreSQL, Docker, интеграции и системное проектирование.</p>'
    )
    interview_fastapi.lesson_materials = render_materials(
        (
            ('Вопросы для Python-собеседования', 'https://github.com/yakimka/python_interview_questions'),
            ('Карта знаний backend-разработчика', 'https://roadmap.sh/backend'),
        ),
        'Пройдите итоговое интервью и защитите архитектуру ЭДО. Объясните выбор технологий, конкурентную модель, хранение документов, права, обработку ошибок, тестирование и возможные узкие места.',
    )

    collections_quiz = clone_collections_quiz(apps)
    django_quiz = Quiz.objects.filter(pk=14).first()
    if django_quiz:
        django_quiz.title = 'Django: проект, ORM и кеширование'
        django_quiz.save(update_fields=('title',))
    quiz_by_id = {
        quiz.pk: quiz
        for quiz in Quiz.objects.filter(pk__in=(9, 11, 12, 13, 14, 15))
    }
    if collections_quiz:
        quiz_by_id[collections_quiz.pk] = collections_quiz

    # После перестановки интервью объектные ссылки в ordered сохраняются.
    final_by_position = {
        schedule.position: schedule
        for schedule in ordered
    }
    quiz_targets = (
        (10, quiz_by_id.get(9), 'Python: переменные, условия и строки'),
        (27, collections_quiz, 'Python: циклы, словари и коллекции'),
        (55, quiz_by_id.get(11), 'Python: функции, файлы и исключения'),
        (67, quiz_by_id.get(12), 'ООП: классы, наследование и полиморфизм'),
        (74, quiz_by_id.get(13), 'ООП: проектирование и тестирование'),
        (144, quiz_by_id.get(14), 'Django: проект, ORM и кеширование'),
        (157, quiz_by_id.get(15), 'Django: запросы, оптимизация и DRF'),
    )
    for position, quiz, label in quiz_targets:
        if quiz:
            final_by_position[position].lesson_materials = add_quiz_link(
                final_by_position[position].lesson_materials,
                quiz,
                label,
            )

    Schedule.objects.bulk_update(
        ordered,
        fields=(
            'position', 'theme', 'lesson_type', 'plan', 'lesson_materials',
        ),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0017_rebuild_backend_web_curriculum'),
        ('questionnaire', '0018_quiz_archive_state'),
    ]

    operations = [
        migrations.RunPython(refine_curriculum, migrations.RunPython.noop),
    ]
