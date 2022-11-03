from ckeditor.fields import RichTextField
from ckeditor_uploader.fields import RichTextUploadingField
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Review(models.Model):
    class Meta:
        db_table = "Отзывы"
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    author_id = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Автор")
    content = RichTextField(max_length=1000, verbose_name="Текст")
    pub_date = models.DateTimeField("Дата публикации", default=timezone.now)

    def __str__(self):
        return self.content[0:200]
