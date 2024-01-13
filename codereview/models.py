from ckeditor_uploader.fields import RichTextUploadingField
from django.db import models

from Course.models import Student


class ProjectCategories(models.Model):
    title = models.CharField(max_length=48, unique=True,
                             verbose_name='Название')
    min_lines = models.PositiveIntegerField(
        verbose_name='Минимальное кол-во строк')
    min_cognetive = models.PositiveIntegerField(
        verbose_name='Минимальная когнитивная сложность')
    max_cognetive = models.PositiveIntegerField(
        verbose_name='Максимальная когнитивная сложность', default=9999)

    def __str__(self):
        return f'{self.title}'

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'


class ProjectForReview(models.Model):
    category = models.ForeignKey(
        ProjectCategories,
        on_delete=models.CASCADE,
        verbose_name='Категория',
        related_name='project_review',
    )
    user = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        verbose_name='Ученик',
        related_name='code_reviews',
    )
    github = models.URLField(verbose_name='GitHub')
    comment = models.TextField(verbose_name='Комментарий ученика',
                               default='Нет комментария')
    status = models.BooleanField(verbose_name='Проведено', default=False)
    lines = models.PositiveIntegerField(
        verbose_name='Кол-во строк',
        null=True,
    )
    cognetive = models.PositiveIntegerField(
        verbose_name='Когнитивная сложность',
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='Отправлен')

    def __str__(self):
        return f'{self.user}, {self.created_at}'

    class Meta:
        verbose_name = 'Заявка на ревью'
        verbose_name_plural = 'Заявки на ревью'


class CodeReview(models.Model):
    project = models.ForeignKey(
        ProjectForReview,
        on_delete=models.CASCADE,
        verbose_name='Проект',
        related_name='code_review',
    )
    status = models.BooleanField(verbose_name='Пройдено', default=False)
    review = RichTextUploadingField(
        verbose_name='Ревью',
    )
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='Отправлено')

    def __str__(self):
        return f'{self.project}, {self.status}'

    class Meta:
        verbose_name = 'Ревью'
        verbose_name_plural = 'Ревью'
