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



