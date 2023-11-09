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
    title = models.CharField(max_length=256, verbose_name='Вопрос', unique=True)
    theme = models.ForeignKey(InterviewQuestionCategory,
                              verbose_name='Категория',
                              related_name='interview_questions',
                              on_delete=models.SET_NULL,
                              null=True)
    percent = models.PositiveIntegerField(
        verbose_name='Вероятность встретить (%)'
    )

    def __str__(self):
        return f'{self.title}'

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ('-percent',)
