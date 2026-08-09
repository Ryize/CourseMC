from django.conf import settings
from django.db import models


class InterviewQuestionCategory(models.Model):
    title = models.CharField(max_length=32, unique=True,
                             verbose_name='Название')

    def __str__(self):
        return f'{self.title}'

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'


class InterviewQuestion(models.Model):
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

    def __str__(self):
        return f'{self.title}'

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
