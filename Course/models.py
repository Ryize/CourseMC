import os
import random
import uuid

from ckeditor_uploader.fields import RichTextUploadingField
from django.contrib.auth.models import User
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models import Max
from django.db.models.signals import post_delete
from django.dispatch import receiver


def generate_student_password():
    return random.randint(1111, 9999)


class PrivateLessonSolutionStorage(FileSystemStorage):
    """Хранилище вне MEDIA_ROOT: файлы выдаются только защищённым view."""

    @property
    def base_location(self):
        return str(settings.PRIVATE_SOLUTION_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)


def lesson_solution_upload_to(instance, filename):
    """Сохраняет работы в непредсказуемом пути без исходного имени файла."""
    extension = os.path.splitext(filename)[1].lower()
    return (
        f'solution_uploads/{instance.solution.student_id}/'
        f'{uuid.uuid4().hex}{extension}'
    )


class Student(models.Model):
    name = models.CharField(max_length=32, verbose_name='Имя')
    contact = models.CharField(max_length=128, verbose_name='Контакты')
    email = models.EmailField(max_length=64,
                              unique=False,
                              verbose_name='Почта'
                              )
    password = models.CharField(
        max_length=128, verbose_name='Пароль',
        default=generate_student_password,
    )
    groups = models.ForeignKey(
        'LearnGroup',
        on_delete=models.CASCADE,
        verbose_name='Группа обучения',
        default=2,
        related_name='students',
    )
    is_learned = models.BooleanField(default=False, verbose_name='Учащийся')
    direction = models.ManyToManyField(
        "DirectionStudy", related_name="students", verbose_name="Направление",
    )
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='Зарегестрирован')

    class Meta:
        verbose_name = 'Ученик'
        verbose_name_plural = 'Ученики'

    def __str__(self):
        return f'{self.name}'


class LearnGroup(models.Model):
    title = models.CharField(max_length=32, verbose_name='Название')
    is_studies = models.BooleanField(default=False,
                                     verbose_name='Идут занятия')
    teacher = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        verbose_name='Учитель',
        related_name='learngroups',
    )
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='Создана')

    class Meta:
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'

    def __str__(self):
        return f'{self.title}'


class DirectionStudy(models.Model):
    title = models.CharField(max_length=48, unique=True,
                             verbose_name='Название')

    def __str__(self):
        return f'{self.title}'

    class Meta:
        verbose_name = 'Направление'
        verbose_name_plural = 'Направления'


class Schedule(models.Model):
    LESSON_TYPE_CHOICES = (
        ('Практика', 'Практика'),
        ('Новая тема', 'Новая тема'),
        ('Ключевой урок', 'Ключевой урок'),
    )
    theme = models.CharField(
        max_length=128, verbose_name='Тема урока', default='Тема не задана!'
    )
    plan = RichTextUploadingField(
        verbose_name='План урока',
        unique=False,
        default='План не указан!',
    )
    lesson_materials = RichTextUploadingField(
        verbose_name='Материалы к уроку',
        unique=False,
        default='Дополнительных материалов нету!',
    )
    lesson_type = models.CharField(
        max_length=64,
        choices=LESSON_TYPE_CHOICES,
        default='Практика',
        verbose_name='Тип урока',
    )

    direction = models.ForeignKey(
        DirectionStudy,
        on_delete=models.PROTECT,
        verbose_name='Направление',
        related_name='schedules',
        default=1,
    )

    position = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name='Порядок в программе',
        help_text='Назначается автоматически. Изменяйте порядок через админку.',
    )
    is_archived = models.BooleanField(
        default=False,
        verbose_name='В архиве',
        help_text='Архивный урок не показывается ученикам и не удаляет их работы.',
    )

    for_filter = models.IntegerField(default=100)

    class Meta:
        verbose_name = 'Расписание'
        verbose_name_plural = 'Расписания'
        ordering = ('direction_id', 'position', 'pk')
        indexes = [
            models.Index(
                fields=('direction', 'position'),
                name='course_sched_dir_pos_idx',
            ),
        ]

    def save(self, *args, **kwargs):
        """Новые уроки без позиции добавляются в конец своего направления."""
        if not self.position and self.direction_id:
            last_position = (
                type(self).objects
                .filter(
                    direction_id=self.direction_id,
                    is_archived=self.is_archived,
                )
                .aggregate(last_position=Max('position'))['last_position']
                or 0
            )
            self.position = last_position + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.theme}'


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
    duration = models.TimeField(verbose_name='Продолжительность',
                                default='1:00:00')

    class Meta:
        verbose_name = 'Время занятия'
        verbose_name_plural = 'Время занятий'

    def __str__(self):
        return f'{self.group}, {self.weekday}-{self.time_lesson}'


class ApplicationsForTraining(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        verbose_name='Ученик',
        related_name='app_training',
    )
    ip = models.GenericIPAddressField(verbose_name='IP')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Оставлена',
    )
    descry = models.BooleanField(default=False, verbose_name='Рассмотрена')

    def __str__(self):
        return f'{self.student}, {self.descry}'

    class Meta:
        verbose_name = 'Заявка на обучение'
        verbose_name_plural = 'Заявки на обучение'
        ordering = ('descry',)


class AdditionalLessons(models.Model):
    group = models.ForeignKey(
        'LearnGroup',
        on_delete=models.CASCADE,
        verbose_name='Группа обучения',
        related_name='additional_lessons',
    )
    amount = models.IntegerField(verbose_name='Количество')

    def __str__(self):
        return f'Сдвиг у {self.group} на {self.amount}'

    class Meta:
        verbose_name = 'Сдвиг расписания'
        verbose_name_plural = 'Сдвиг расписаний'


class LessonSolution(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'На проверке'
        ACCEPTED = 'accepted', 'Принято'
        NEEDS_REVISION = 'needs_revision', 'Нужна доработка'

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='solutions',
        verbose_name='Урок',
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='lesson_solutions',
        verbose_name='Ученик',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Статус проверки',
    )
    teacher_comment = models.TextField(
        blank=True,
        verbose_name='Комментарий преподавателя',
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_lesson_solutions',
        verbose_name='Проверил',
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Проверено',
    )
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Решение урока'
        verbose_name_plural = 'Решения уроков'
        constraints = [
            models.UniqueConstraint(
                fields=('schedule', 'student'),
                name='one_solution_per_lesson_and_student',
            ),
        ]
        ordering = ('status', '-updated_at')

    def __str__(self):
        return f'{self.student}: {self.schedule}'


class LessonSolutionFile(models.Model):
    solution = models.ForeignKey(
        LessonSolution,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Решение урока',
    )
    file = models.FileField(
        upload_to=lesson_solution_upload_to,
        storage=PrivateLessonSolutionStorage(),
        verbose_name='Файл',
    )
    original_name = models.CharField(max_length=255, verbose_name='Имя файла')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Загружен')

    class Meta:
        verbose_name = 'Файл решения'
        verbose_name_plural = 'Файлы решений'
        ordering = ('uploaded_at',)

    def __str__(self):
        return self.original_name


@receiver(post_delete, sender=LessonSolutionFile)
def delete_lesson_solution_file(sender, instance, **kwargs):
    """Удаляет файл из закрытого хранилища вслед за записью в базе."""
    if instance.file:
        instance.file.delete(save=False)
