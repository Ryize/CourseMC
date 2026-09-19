import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class PrivateMockInterviewStorage(FileSystemStorage):
    """Закрытое хранилище заданий и решений мок-собеседований."""

    @property
    def base_location(self):
        return str(settings.PRIVATE_SOLUTION_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)


def mock_task_upload_to(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    return f'mock_interview_tasks/{uuid.uuid4().hex}{extension}'


def mock_solution_upload_to(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    return f'mock_interview_solutions/{instance.interview_id}/{uuid.uuid4().hex}{extension}'


class InterviewQuestionCategory(models.Model):
    title = models.CharField(max_length=32, unique=True,
                             verbose_name='Название')

    def __str__(self):
        return f'{self.title}'

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'


class InterviewQuestion(models.Model):
    class MockSection(models.TextChoices):
        GENERAL = 'general', 'Общие вопросы'
        PYTHON = 'python', 'Python'
        OOP = 'oop', 'ООП'
        FRAMEWORK = 'framework', 'Фреймворки'

    class MockLevel(models.TextChoices):
        JUNIOR = 'junior', 'Junior'
        MIDDLE = 'middle', 'Middle'
        SENIOR = 'senior', 'Senior'

    hard_level = [(i, i) for i in range(1, 11)]
    title = models.CharField(max_length=256, verbose_name='Вопрос',
                             unique=True)
    theme = models.ForeignKey(InterviewQuestionCategory,
                              verbose_name='Категория',
                              related_name='interview_questions',
                              on_delete=models.SET_NULL,
                              null=True)
    percent = models.PositiveIntegerField(
        verbose_name='Вероятность встретить (%)'
    )
    complexity = models.IntegerField(choices=hard_level, default=1,
                                  verbose_name='Сложность')
    use_in_mock = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Использовать в мок-собеседовании',
    )
    mock_section = models.CharField(
        max_length=16,
        choices=MockSection.choices,
        blank=True,
        verbose_name='Блок мок-собеседования',
    )
    mock_level = models.CharField(
        max_length=12,
        choices=MockLevel.choices,
        default=MockLevel.JUNIOR,
        db_index=True,
        verbose_name='Уровень мок-собеседования',
    )

    def __str__(self):
        return f'{self.title}'

    def clean(self):
        super().clean()
        if self.use_in_mock and not self.mock_section:
            raise ValidationError({
                'mock_section': 'Выберите блок мок-собеседования.',
            })

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ('-percent',)


class InterviewQuestionProgress(models.Model):
    """Личная история показа вопросов для тренировки собеседования."""

    class Status(models.TextChoices):
        UNRATED = 'unrated', 'Не оценен'
        ANSWERED = 'answered', 'Ответил'
        REPEAT = 'repeat', 'Повторить'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='interview_question_progress',
        verbose_name='Пользователь',
    )
    question = models.ForeignKey(
        InterviewQuestion,
        on_delete=models.CASCADE,
        related_name='progress_entries',
        verbose_name='Вопрос',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.REPEAT,
        verbose_name='Статус',
    )
    last_shown_at = models.DateTimeField(verbose_name='Последний показ')
    next_available_at = models.DateTimeField(
        db_index=True,
        verbose_name='Можно показать снова',
    )
    shown_count = models.PositiveIntegerField(default=1, verbose_name='Показов')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлён')

    class Meta:
        verbose_name = 'Прогресс вопроса собеседования'
        verbose_name_plural = 'Прогресс вопросов собеседования'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'question'),
                name='interview_progress_user_question_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=('user', 'status', 'next_available_at'),
                name='intrv_prog_user_stat_idx',
            ),
        ]


class LiveCodingTask(models.Model):
    """Задание практической части тестового собеседования."""

    class Category(models.TextChoices):
        PYTHON = 'python', 'Python'
        OOP = 'oop', 'ООП'
        DJANGO = 'django', 'Django'
        FASTAPI = 'fastapi', 'FastAPI'
        ALGORITHMS = 'algorithms', 'Алгоритмы'

    class Level(models.TextChoices):
        JUNIOR = 'junior', 'Junior'
        MIDDLE = 'middle', 'Middle'

    hard_level = [(i, i) for i in range(1, 11)]

    title = models.CharField(max_length=180, verbose_name='Название')
    description = models.TextField(verbose_name='Условие задания')
    category = models.CharField(
        max_length=16,
        choices=Category.choices,
        default=Category.PYTHON,
        db_index=True,
        verbose_name='Категория',
    )
    level = models.CharField(
        max_length=12,
        choices=Level.choices,
        default=Level.JUNIOR,
        db_index=True,
        verbose_name='Уровень',
    )
    starter_file = models.FileField(
        upload_to=mock_task_upload_to,
        storage=PrivateMockInterviewStorage(),
        blank=True,
        verbose_name='Файл с заданием',
    )
    frameworks = models.ManyToManyField(
        InterviewQuestionCategory,
        blank=True,
        related_name='live_coding_tasks',
        verbose_name='Фреймворки',
        help_text='Пустой список означает универсальное задание.',
    )
    complexity = models.IntegerField(
        choices=hard_level,
        default=3,
        verbose_name='Сложность',
    )
    duration_minutes = models.PositiveSmallIntegerField(
        default=30,
        verbose_name='Время выполнения, минут',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Задание лайвкодинга'
        verbose_name_plural = 'Задания лайвкодинга'
        ordering = ('category', 'level', 'title', 'pk')

    def __str__(self):
        return self.title


class MockInterviewSettings(models.Model):
    """Единственная запись с общими ограничениями мок-собеседований."""

    weekly_attempt_limit = models.PositiveSmallIntegerField(
        default=3,
        validators=(MaxValueValidator(100),),
        verbose_name='Попыток за 7 дней',
        help_text=(
            'Считаются все начатые попытки, включая прерванные. '
            'Укажите 0, чтобы временно запретить новые собеседования.'
        ),
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    @classmethod
    def load(cls):
        settings_object, _ = cls.objects.get_or_create(pk=1)
        return settings_object

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return 'Ограничения мок-собеседований'

    class Meta:
        verbose_name = 'Настройки мок-собеседований'
        verbose_name_plural = 'Настройки мок-собеседований'


class MockInterview(models.Model):
    """Одна неизменяемая после завершения попытка мок-собеседования."""

    class Status(models.TextChoices):
        THEORY = 'theory', 'Теоретическая часть'
        LIVE_CODING = 'live_coding', 'Лайвкодинг'
        ANALYZING = 'analyzing', 'Анализируется'
        COMPLETED = 'completed', 'Завершено'
        FAILED = 'failed', 'Ошибка анализа'
        ABANDONED = 'abandoned', 'Прервано'

    class Level(models.TextChoices):
        JUNIOR = 'junior', 'Junior'
        MIDDLE = 'middle', 'Middle'
        SENIOR = 'senior', 'Senior'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='mock_interviews',
        verbose_name='Ученик',
    )
    frameworks = models.ManyToManyField(
        InterviewQuestionCategory,
        blank=True,
        related_name='mock_interviews',
        verbose_name='Выбранные фреймворки',
    )
    level = models.CharField(
        max_length=12,
        choices=Level.choices,
        default=Level.JUNIOR,
        db_index=True,
        verbose_name='Уровень собеседования',
    )
    live_coding_task = models.ForeignKey(
        LiveCodingTask,
        on_delete=models.PROTECT,
        related_name='interviews',
        null=True,
        blank=True,
        verbose_name='Задание лайвкодинга',
    )
    task_title = models.CharField(
        max_length=180,
        blank=True,
        verbose_name='Название задания на момент прохождения',
    )
    task_description = models.TextField(
        blank=True,
        verbose_name='Условие задания на момент прохождения',
    )
    live_coding_answer = models.TextField(
        blank=True,
        verbose_name='Решение лайвкодинга',
    )
    live_coding_repository_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Ссылка на Git-репозиторий',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.THEORY,
        db_index=True,
        verbose_name='Статус',
    )
    theory_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Теория, %',
    )
    live_coding_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Лайвкодинг, %',
    )
    overall_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Итог, %',
    )
    summary = models.TextField(blank=True, verbose_name='Краткий итог')
    live_coding_comment = models.TextField(
        blank=True,
        verbose_name='Комментарий по лайвкодингу',
    )
    strengths = models.JSONField(default=list, blank=True, verbose_name='Сильные стороны')
    weaknesses = models.JSONField(default=list, blank=True, verbose_name='Что повторить')
    ai_model = models.CharField(max_length=80, blank=True, verbose_name='Модель ИИ')
    ai_error = models.TextField(blank=True, verbose_name='Ошибка анализа')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='Начато')
    theory_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Теория завершена',
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Завершено',
    )
    analysis_started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Анализ запущен',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Мок-собеседование'
        verbose_name_plural = 'История мок-собеседований'
        ordering = ('-started_at', '-pk')

    def __str__(self):
        return f'{self.user}: {self.started_at:%d.%m.%Y %H:%M}'


class MockInterviewAnswer(models.Model):
    class Section(models.TextChoices):
        GENERAL = 'general', 'Общие вопросы'
        PYTHON = 'python', 'Python'
        OOP = 'oop', 'ООП'
        FRAMEWORK = 'framework', 'Фреймворки'

    class Result(models.TextChoices):
        NOT_EVALUATED = 'not_evaluated', 'Не оценено'
        GOOD = 'good', 'Хорошо'
        PARTIAL = 'partial', 'Частично'
        WRONG = 'wrong', 'Неправильно'

    interview = models.ForeignKey(
        MockInterview,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Мок-собеседование',
    )
    original_question = models.ForeignKey(
        InterviewQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mock_answers',
        verbose_name='Исходный вопрос',
    )
    section = models.CharField(
        max_length=16,
        choices=Section.choices,
        verbose_name='Раздел',
    )
    category_snapshot = models.CharField(max_length=64, verbose_name='Категория')
    question_snapshot = models.CharField(max_length=500, verbose_name='Вопрос')
    answer_text = models.TextField(blank=True, verbose_name='Ответ ученика')
    result = models.CharField(
        max_length=16,
        choices=Result.choices,
        default=Result.NOT_EVALUATED,
        verbose_name='Оценка ответа',
    )
    ai_comment = models.TextField(
        blank=True,
        verbose_name='Комментарий к ошибке',
    )
    position = models.PositiveSmallIntegerField(verbose_name='Порядок')

    class Meta:
        verbose_name = 'Ответ мок-собеседования'
        verbose_name_plural = 'Ответы мок-собеседования'
        ordering = ('position', 'pk')
        constraints = [
            models.UniqueConstraint(
                fields=('interview', 'position'),
                name='unique_mock_interview_answer_position',
            ),
        ]

    def __str__(self):
        return f'{self.interview}: вопрос {self.position}'


class MockInterviewFile(models.Model):
    interview = models.ForeignKey(
        MockInterview,
        on_delete=models.CASCADE,
        related_name='solution_files',
        verbose_name='Мок-собеседование',
    )
    file = models.FileField(
        upload_to=mock_solution_upload_to,
        storage=PrivateMockInterviewStorage(),
        verbose_name='Файл решения',
    )
    original_name = models.CharField(max_length=255, verbose_name='Имя файла')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Загружен')

    class Meta:
        verbose_name = 'Файл мок-собеседования'
        verbose_name_plural = 'Файлы мок-собеседований'
        ordering = ('uploaded_at', 'pk')

    def __str__(self):
        return self.original_name


@receiver(post_delete, sender=LiveCodingTask)
def delete_mock_task_file(sender, instance, **kwargs):
    if instance.starter_file:
        instance.starter_file.delete(save=False)


@receiver(post_delete, sender=MockInterviewFile)
def delete_mock_solution_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
