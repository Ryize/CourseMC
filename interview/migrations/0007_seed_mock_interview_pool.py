from django.db import migrations


GENERAL_QUESTIONS = (
    'Что такое HTTP и HTTPs',
    'Какие основные HTTP методы знаешь',
    'Какие есть коды ответов HTTP',
    'В чем суть принципа REST',
    'Что такое TCP/IP',
    'Что такое TCP',
    'Что такое UDP',
    'Что такое DNS и как он работает',
    'Что такое клиент-серверная архитектура',
    'Что такое WebSocket',
    'Что такое индексы и как они работают',
    'Что такое Acid в SQL',
    'Что такое транзакция',
    'Какие базы данных использовал в работе',
    'Что знаешь про нормализацию',
    'Что такое git',
    'Отличия rebase от merge',
    'Какие основные команды Git вам известны',
    'Что такое Docker',
    'Что такое Docker Compose',
    'Какая разница между аутентификацией и авторизацией',
    'Чем отличается микросервисная архитектура от монолитной',
)

GENERAL_SEEDED_QUESTIONS = (
    ('Что такое база данных и для чего она нужна?', 15, 1),
    ('Какие протоколы передачи данных вы знаете и чем TCP отличается от UDP?', 14, 2),
    ('Что такое Git и для чего разработчику система контроля версий?', 15, 1),
    ('Что происходит после ввода адреса сайта в браузере?', 12, 3),
)

PYTHON_QUESTIONS = (
    'В чем разница между итератором и генератором',
    'Что такое декораторы',
    'Чем init() отличается от new()',
    'Что такое итератор',
    'Что может быть ключем в словаре',
    'Что такое MRO',
    'Что такое контекстный менеджер',
    'Что такое магические методы',
    'В чем отличие списка от кортежа',
    'Что такое list comprehension',
    'Что делает декоратор property',
    'Что такое генератор',
    'В чем разница сравнение через is и "=="',
    'Python компилируемый или интерпретируемый',
    'Что такое GIL',
    'Чем отличаются декораторы classmethod и staticmethod',
    'Какие есть типы данных в Python',
    'Какие знаешь изменяемые и неизменяемые типы данных',
    'Почему нельзя делать мутабельные типы дефолтными аргументами функции',
    'Как в Python происходит поиск переменной по области видимости',
    'Расскажи про иерархию исключений Python',
    'Как в функцию передаются аргументы, по ссылке или по значению',
)

OOP_QUESTIONS = (
    'Что такое SOLID',
    'Какие знаешь принципы ООП',
    'Что такое полиморфизм',
    'Расскажи про ООП в программировании',
    'Что знаешь о наследовании',
    'Что такое миксин',
    'Расскажи о инкапсуляции',
    'Зачем нужен метод super в классе',
    'Что такое абстрактные классы',
    'Что такое self',
    'Что такое классы',
    'В чем преимущество ООП перед обычными функциями',
    'В чем разница методов экземпляра, класса и статическими',
    'Чем отличается атрибут класса от атрибута объекта',
    'Принципы ООП - агрегация/композиция',
)

DJANGO_QUESTIONS = (
    'Что такое Django и почему его используют?',
    'Опишите архитектуру Django',
    'Что такое DRF?',
    'Что такое management команды в Django?',
    'Как работает middleware',
    'Каков цикл запроса в Django?',
    'В чем разница между select_related и prefetch_related?',
    'Перечислите методы Django ORM',
    'Зачем параметр on_delete в поле ForeignKey модели django? Какие параметры принимает атрибут?',
    'Реализация csrf в Django',
    'Что такое Q в Django ORM?',
    'Как реализован many to many в Django',
    'Что означает ленивые querySet()',
    'Как сгенерировать и применить миграцию',
    'Что такое FBV и CBV в Django?',
)

FLASK_QUESTIONS = (
    ('Почему предпочитаешь Flask', 3, 1),
    ('Что такое Flask и в каких проектах его удобно использовать?', 12, 2),
    ('Как во Flask устроена маршрутизация?', 10, 2),
    ('Что такое контекст приложения и контекст запроса во Flask?', 8, 4),
    ('Как во Flask обрабатываются конфигурация и переменные окружения?', 8, 3),
    ('Как организовать структуру большого Flask-приложения?', 8, 4),
    ('Что такое Blueprint во Flask и зачем он нужен?', 10, 3),
    ('Как во Flask подключить базу данных и миграции?', 8, 3),
    ('Как реализовать обработку ошибок во Flask?', 7, 3),
    ('Чем Flask отличается от Django?', 12, 2),
)

FASTAPI_QUESTIONS = (
    ('Что такое FastAPI и в каких проектах его удобно использовать?', 15, 2),
    ('Как FastAPI использует аннотации типов и Pydantic?', 14, 3),
    ('Как во FastAPI объявляются path, query и body параметры?', 12, 3),
    ('Что такое dependency injection во FastAPI?', 12, 4),
    ('Как во FastAPI обрабатываются ошибки и HTTPException?', 10, 3),
    ('Когда endpoint во FastAPI следует объявлять через async def?', 12, 4),
    ('Как во FastAPI устроена автоматическая OpenAPI-документация?', 8, 3),
    ('Как реализовать аутентификацию во FastAPI?', 10, 4),
    ('Как тестировать FastAPI-приложение?', 8, 4),
    ('Чем FastAPI отличается от Flask и Django?', 12, 3),
)


def seed_mock_pool(apps, schema_editor):
    Category = apps.get_model('interview', 'InterviewQuestionCategory')
    Question = apps.get_model('interview', 'InterviewQuestion')
    Task = apps.get_model('interview', 'LiveCodingTask')

    def ensure_pool(titles, category_title, section, percent, complexity):
        category, _ = Category.objects.get_or_create(title=category_title)
        for title in titles:
            question, _ = Question.objects.get_or_create(
                title=title,
                defaults={
                    'theme': category,
                    'percent': percent,
                    'complexity': complexity,
                },
            )
            question.use_in_mock = True
            question.mock_section = section
            question.save(update_fields=('use_in_mock', 'mock_section'))

    ensure_pool(
        GENERAL_QUESTIONS, 'Общая разработка', 'general', 8, 2,
    )
    ensure_pool(PYTHON_QUESTIONS, 'Python', 'python', 10, 3)
    ensure_pool(OOP_QUESTIONS, 'ООП', 'oop', 10, 3)
    ensure_pool(DJANGO_QUESTIONS, 'Django', 'framework', 10, 3)

    general_category, _ = Category.objects.get_or_create(title='Общая разработка')
    for title, percent, complexity in GENERAL_SEEDED_QUESTIONS:
        question, _ = Question.objects.get_or_create(
            title=title,
            defaults={
                'theme': general_category,
                'percent': percent,
                'complexity': complexity,
            },
        )
        question.theme = general_category
        question.percent = percent
        question.complexity = complexity
        question.use_in_mock = True
        question.mock_section = 'general'
        question.save(update_fields=(
            'theme', 'percent', 'complexity', 'use_in_mock', 'mock_section',
        ))

    for category_title, questions in (
        ('Flask', FLASK_QUESTIONS),
        ('FastAPI', FASTAPI_QUESTIONS),
    ):
        category, _ = Category.objects.get_or_create(title=category_title)
        for title, percent, complexity in questions:
            question, _ = Question.objects.get_or_create(
                title=title,
                defaults={
                    'theme': category,
                    'percent': percent,
                    'complexity': complexity,
                },
            )
            question.theme = category
            question.percent = percent
            question.complexity = complexity
            question.use_in_mock = True
            question.mock_section = 'framework'
            question.save(update_fields=(
                'theme', 'percent', 'complexity', 'use_in_mock', 'mock_section',
            ))

    Task.objects.get_or_create(
        title='API списка задач с фильтрацией',
        defaults={
            'description': (
                'Реализуйте небольшой REST API для списка задач. У задачи есть '
                'название, описание, статус и дата создания. Нужны создание и '
                'получение задач, фильтрация по статусу, валидация входных данных '
                'и корректные ответы для ошибок. Можно использовать выбранный '
                'вами фреймворк или написать решение на чистом Python. Добавьте '
                'краткое описание запуска и, если успеете, тесты.'
            ),
            'complexity': 3,
            'duration_minutes': 30,
            'is_active': True,
        },
    )


def unseed_mock_pool(apps, schema_editor):
    Question = apps.get_model('interview', 'InterviewQuestion')
    all_titles = (
        GENERAL_QUESTIONS + PYTHON_QUESTIONS + OOP_QUESTIONS + DJANGO_QUESTIONS
        + tuple(item[0] for item in GENERAL_SEEDED_QUESTIONS + FLASK_QUESTIONS + FASTAPI_QUESTIONS)
    )
    Question.objects.filter(title__in=all_titles).update(
        use_in_mock=False,
        mock_section='',
    )


class Migration(migrations.Migration):
    dependencies = [
        ('interview', '0006_interviewquestion_mock_section_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_mock_pool, unseed_mock_pool),
    ]
