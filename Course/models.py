import random

from ckeditor_uploader.fields import RichTextUploadingField
from django.contrib.auth.models import User
from django.db import models


class Student(models.Model):
    name = models.CharField(max_length=32, verbose_name='Имя')
    contact = models.CharField(max_length=128, verbose_name='Контакты')
    email = models.EmailField(max_length=64,
                              unique=False,
                              verbose_name='Почта'
                              )
    password = models.CharField(
        max_length=128, verbose_name='Пароль', default=random.randint(1111, 9999)
    )
    groups = models.ForeignKey(
        'LearnGroup',
        on_delete=models.CASCADE,
        verbose_name='Группа обучения',
        default=2,
        related_name='students',
    )
    is_learned = models.BooleanField(default=False, verbose_name='Учащийся')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Зарегистрирован')
    # last_session = models.DateTimeField(auto_now_add=True, verbose_name='Последний сеанс', null=True, blank=True)

    class Meta:
        verbose_name = 'Ученик'
        verbose_name_plural = 'Ученики'

    def __str__(self):
        return f'{self.name}'


class LearnGroup(models.Model):
    title = models.CharField(max_length=32, verbose_name='Название')
    is_studies = models.BooleanField(default=False, verbose_name='Идут занятия')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')

    class Meta:
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'

    def __str__(self):
        return f'{self.title}'


class Schedule(models.Model):
    LESSON_TYPE_CHOICES = (
        ('Практика', 'Практика'),
        ('Новая тема', 'Новая тема'),
        ('Ключевой урок', 'Ключевой урок'),
    )

    group = models.ForeignKey(
        'LearnGroup',
        on_delete=models.CASCADE,
        verbose_name='Группа обучения',
        related_name='schedules',
    )
    theme = models.CharField(
        max_length=128, verbose_name='Тема урока', default='Тема не задана!'
    )
    weekday = models.DateField(verbose_name='День недели')
    time_lesson = models.TimeField(verbose_name='Время')
    lesson_materials = RichTextUploadingField(
        verbose_name='Материалы к уроку',
        unique=False,
        default='Дополнительных материалов нету!',
    )
    absent = models.ManyToManyField(
        'Student',
        verbose_name='Отсутствующие',
        null=True,
        blank=True,
        related_name='absents',
    )
    lesson_type = models.CharField(
        max_length=64,
        choices=LESSON_TYPE_CHOICES,
        default='Практика',
        verbose_name='Тип урока',
    )
    is_display = models.BooleanField(default=True, verbose_name='Отображать')

    class Meta:
        verbose_name = 'Расписание'
        verbose_name_plural = 'Расписания'

    def __str__(self):
        return f'{self.group}: {self.weekday}'


class StudentQuestion(models.Model):
    group = models.ForeignKey(
        'LearnGroup',
        on_delete=models.CASCADE,
        verbose_name='Группа обучения',
        related_name='studentquestion',
    )
    question = models.CharField(max_length=512, verbose_name='Вопрос')
    solved = models.BooleanField(default=False, verbose_name='Решён')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Задан', null=True
    )

    class Meta:
        verbose_name = 'Вопрос ученика'
        verbose_name_plural = 'Вопросы учеников'

    def __str__(self):
        return f'{self.question}, {self.group}'


class ClassesTimetable(models.Model):
    WEEKDAY = (
        ('Понедельник', 'Понедельник'),
        ('Вторник', 'Вторник'),
        ('Среда', 'Среда'),
        ('Четверг', 'Четверг'),
        ('Пятница', 'Пятница'),
        ('Суббота', 'Суббота'),
        ('Воскресенье', 'Воскресенье'),
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Учитель',
        related_name='timelesson',
    )
    group = models.ForeignKey(
        'LearnGroup',
        on_delete=models.CASCADE,
        verbose_name='Группа обучения',
        related_name='classtime',
    )
    weekday = models.CharField(
        max_length=64,
        choices=WEEKDAY,
        default='Понедельник',
        verbose_name='День недели',
    )
    time_lesson = models.TimeField(verbose_name='Время')
    duration = models.TimeField(verbose_name='Продолжительность', default='1:00:00')

    class Meta:
        verbose_name = 'Время занятия'
        verbose_name_plural = 'Время занятий'

    def __str__(self):
        return f'{self.group}, {self.weekday}-{self.time_lesson}'
