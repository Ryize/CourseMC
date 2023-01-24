from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Category(models.Model):
    title = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.title


class TodoList(models.Model):
    title = models.CharField(max_length=250)
    content = models.TextField(blank=True)
    category = models.ForeignKey(Category, default=1, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    due_date = models.DateField(default=timezone.now().strftime("%Y-%m-%d"))
    created_at = models.DateField(default=timezone.now().strftime("%Y-%m-%d"))

    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


if not Category.objects.all().count():
    Category.objects.create(title='Общее')
