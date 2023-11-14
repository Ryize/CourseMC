from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from Course.models import LearnGroup


class Category(models.Model):
    title = models.CharField(max_length=100, verbose_name='Название')

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.title


class TodoList(models.Model):
    title = models.CharField(max_length=250, verbose_name='Заголовок')
    content = models.TextField(blank=True, verbose_name='Текст')
    category = models.ForeignKey(Category, default=1, on_delete=models.CASCADE, verbose_name='Категория')
    due_date = models.DateField(default=timezone.now().strftime("%Y-%m-%d"), verbose_name='Дата')
    created_at = models.DateField(default=timezone.now().strftime("%Y-%m-%d"), verbose_name='Создано')

    def __str__(self):
        return self.title


class TodoListUser(TodoList):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')

    class Meta:
        verbose_name = 'Пользовательская'
        verbose_name_plural = 'Пользовательские'
        ordering = ["-created_at"]


class TodoListGroup(TodoList):
    group = models.ForeignKey(LearnGroup, on_delete=models.CASCADE, verbose_name='Группа')

    class Meta:
        verbose_name = 'Групповая'
        verbose_name_plural = 'Групповые'
        ordering = ["-created_at"]
