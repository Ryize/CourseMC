from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from Course.models import LearnGroup


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
    due_date = models.DateField(default=timezone.now().strftime("%Y-%m-%d"))
    created_at = models.DateField(default=timezone.now().strftime("%Y-%m-%d"))

    def __str__(self):
        return self.title


class TodoListUser(TodoList):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Пользовательская'
        verbose_name_plural = 'Пользовательские'
        ordering = ["-created_at"]


class TodoListGroup(TodoList):
    group = models.ForeignKey(LearnGroup, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Групповая'
        verbose_name_plural = 'Групповые'
        ordering = ["-created_at"]


categories = ['работа', 'активность', 'сроки', 'события', 'платежи',
              'проекты', 'дела', 'встречи', 'учёба', 'проект']

for category in categories:
    Category.objects.get_or_create(title=category.title())
