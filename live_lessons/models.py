import uuid
import os
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class LiveLesson(models.Model):
    class Origin(models.TextChoices):
        GROUP_SCHEDULE = 'group_schedule', 'По графику группы'
        EXTRA = 'extra', 'Вне графика'

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Запланировано'
        LIVE = 'live', 'Идёт занятие'
        ENDED = 'ended', 'Завершено'
        CANCELLED = 'cancelled', 'Отменено'

    class Audience(models.TextChoices):
        GROUPS = 'groups', 'Выбранные группы'
        OPEN = 'open', 'Любой по ссылке'

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    group = models.ForeignKey(
        'Course.LearnGroup', on_delete=models.PROTECT, null=True, blank=True,
        related_name='live_lessons',
        verbose_name='Учебная группа',
    )
    additional_groups = models.ManyToManyField(
        'Course.LearnGroup', blank=True, related_name='additional_live_lessons',
        verbose_name='Дополнительные группы',
    )
    audience = models.CharField(
        max_length=8, choices=Audience.choices, default=Audience.GROUPS,
        verbose_name='Кому доступно',
    )
    teacher = models.ForeignKey(
        'Course.Student', on_delete=models.PROTECT, related_name='hosted_live_lessons',
        verbose_name='Преподаватель',
    )
    title = models.CharField(max_length=160, verbose_name='Тема занятия')
    scheduled_at = models.DateTimeField(verbose_name='Дата и время')
    duration_minutes = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(15), MaxValueValidator(240)],
        verbose_name='Длительность, минут',
    )
    origin = models.CharField(
        max_length=20, choices=Origin.choices, default=Origin.EXTRA,
        verbose_name='Основание',
    )
    curriculum_lesson = models.ForeignKey(
        'Course.Schedule', on_delete=models.PROTECT, null=True, blank=True,
        related_name='live_lessons', verbose_name='Тема программы',
    )
    timetable_slot = models.ForeignKey(
        'Course.ClassesTimetable', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='live_lessons', verbose_name='Слот графика группы',
    )
    timetable_date = models.DateField(
        null=True, blank=True, editable=False, verbose_name='Исходный день графика',
    )
    room_cleanup_pending = models.BooleanField(default=False, editable=False)
    waiting_room_enabled = models.BooleanField(default=True, verbose_name='Зал ожидания')
    entry_locked = models.BooleanField(default=False, verbose_name='Закрыт вход новым участникам')
    students_can_unmute = models.BooleanField(default=True, verbose_name='Участникам разрешён микрофон')
    students_can_share_screen = models.BooleanField(default=True, verbose_name='Участникам разрешена демонстрация')
    policy_sync_until = models.DateTimeField(null=True, blank=True, editable=False)
    mute_all_pending = models.BooleanField(default=False, editable=False)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.SCHEDULED,
        verbose_name='Статус', db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Начато')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершено')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        ordering = ('scheduled_at', 'pk')
        verbose_name = 'Онлайн-занятие'
        verbose_name_plural = 'Онлайн-занятия'
        indexes = [models.Index(fields=('group', 'scheduled_at'), name='live_group_time_idx')]
        constraints = [models.UniqueConstraint(
            fields=('timetable_slot', 'timetable_date'), name='live_slot_date_once',
        )]

    @property
    def scheduled_end(self):
        return self.scheduled_at + timedelta(minutes=self.duration_minutes)

    @property
    def auto_end_at(self):
        """Начатый урок живёт до полуночи дня начала, остальные — дня расписания."""
        school_timezone = timezone.get_default_timezone()
        day = timezone.localtime(self.started_at or self.scheduled_at, school_timezone).date()
        return timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min), school_timezone)

    def clean(self):
        super().clean()
        self.remember_timetable_date()
        if self.audience == self.Audience.GROUPS and not self.group_id:
            raise ValidationError({'group': 'Выберите основную группу для закрытого занятия.'})
        if self.audience == self.Audience.OPEN and self.group_id:
            raise ValidationError({'group': 'У открытого занятия не должно быть привязанной группы.'})
        if self.audience == self.Audience.OPEN and self.timetable_slot_id:
            raise ValidationError({'timetable_slot': 'Открытый урок не связан с графиком группы.'})
        if self.group_id and self.timetable_slot_id and self.timetable_slot.group_id != self.group_id:
            raise ValidationError({'timetable_slot': 'Слот должен принадлежать выбранной группе.'})
        if self._state.adding and self.group_id and self.teacher_id and self.teacher_id != self.group.teacher_id:
            raise ValidationError({'teacher': 'Преподаватель должен вести выбранную группу.'})
        if self._state.adding and self.timetable_slot_id and self.timetable_date and LiveLesson.objects.filter(
            timetable_slot_id=self.timetable_slot_id, timetable_date=self.timetable_date,
        ).exists():
            raise ValidationError({'timetable_slot': 'Занятие этого дня графика уже создано.'})

    def remember_timetable_date(self):
        if self._state.adding and self.timetable_slot_id and not self.timetable_date and self.scheduled_at:
            self.timetable_date = timezone.localtime(self.scheduled_at, timezone.get_default_timezone()).date()

    def save(self, *args, **kwargs):
        self.remember_timetable_date()
        return super().save(*args, **kwargs)

    @property
    def room_name(self):
        return f'lesson-{self.public_id.hex}'

    def __str__(self):
        return f'{self.title} · {self.group or "Открытый урок"}'


class LiveLessonReschedule(models.Model):
    lesson = models.ForeignKey(
        LiveLesson, on_delete=models.CASCADE, related_name='reschedules',
        verbose_name='Занятие',
    )
    old_scheduled_at = models.DateTimeField(verbose_name='Было назначено на')
    new_scheduled_at = models.DateTimeField(verbose_name='Перенесено на')
    reason = models.CharField(max_length=250, blank=True, verbose_name='Причина')
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='live_lesson_reschedules', verbose_name='Кто перенёс',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Когда перенесено')

    class Meta:
        ordering = ('-created_at', '-pk')
        verbose_name = 'Перенос онлайн-занятия'
        verbose_name_plural = 'Переносы онлайн-занятий'


class LiveLessonRemoval(models.Model):
    lesson = models.ForeignKey(LiveLesson, on_delete=models.CASCADE, related_name='removed_participants')
    identity = models.CharField(max_length=128)
    removed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('lesson', 'identity'), name='live_lesson_removal_once')]


class LiveLessonParticipant(models.Model):
    class Admission(models.TextChoices):
        WAITING = 'waiting', 'Ожидает'
        ADMITTED = 'admitted', 'Допущен'
        DENIED = 'denied', 'Отказано'
        LEFT = 'left', 'Вышел из ожидания'

    lesson = models.ForeignKey(LiveLesson, on_delete=models.CASCADE, related_name='participants')
    identity = models.CharField(max_length=128)
    name = models.CharField(max_length=160)
    admission = models.CharField(max_length=10, choices=Admission.choices, default=Admission.WAITING)
    requested_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    hand_raised_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('lesson', 'identity'), name='live_participant_once')]
        indexes = [models.Index(fields=('lesson', 'admission', 'last_seen_at'), name='live_waiting_seen_idx')]


class PrivateLiveLessonStorage(FileSystemStorage):
    """Вложения чата находятся вне публичного MEDIA_ROOT."""

    @property
    def base_location(self):
        return str(settings.PRIVATE_LIVE_LESSON_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)


def live_lesson_upload_to(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    return f'chat/{instance.message.lesson.public_id.hex}/{uuid.uuid4().hex}{extension}'


def live_lesson_archive_upload_to(instance, filename):
    extension = '.zip' if filename.lower().endswith('.zip') else '.txt'
    return f'archives/{instance.group_id}/{uuid.uuid4().hex}{extension}'


class LiveLessonMessage(models.Model):
    lesson = models.ForeignKey(
        LiveLesson, on_delete=models.CASCADE, related_name='chat_messages',
        verbose_name='Занятие',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='live_lesson_messages', verbose_name='Автор',
    )
    guest_id = models.UUIDField(null=True, blank=True, verbose_name='Идентификатор гостя')
    guest_name = models.CharField(max_length=40, blank=True, verbose_name='Имя гостя')
    body = models.TextField(blank=True, verbose_name='Сообщение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')

    class Meta:
        ordering = ('pk',)
        verbose_name = 'Сообщение занятия'
        verbose_name_plural = 'Сообщения занятий'
        indexes = [
            models.Index(fields=('lesson', 'id'), name='live_chat_lesson_id_idx'),
            models.Index(fields=('lesson', 'guest_id', 'created_at'), name='live_chat_guest_rate_idx'),
        ]
        constraints = [models.CheckConstraint(
            condition=(
                models.Q(author__isnull=False, guest_id__isnull=True, guest_name='') |
                (models.Q(author__isnull=True, guest_id__isnull=False) & ~models.Q(guest_name=''))
            ),
            name='live_chat_one_author',
        )]


class LiveLessonAttachment(models.Model):
    message = models.OneToOneField(
        LiveLessonMessage, on_delete=models.CASCADE, related_name='attachment',
        verbose_name='Сообщение',
    )
    file = models.FileField(
        storage=PrivateLiveLessonStorage(), upload_to=live_lesson_upload_to,
        verbose_name='Файл',
    )
    original_name = models.CharField(max_length=120, verbose_name='Исходное имя')
    content_type = models.CharField(max_length=80, verbose_name='Тип содержимого')
    size = models.PositiveIntegerField(verbose_name='Размер, байт')

    class Meta:
        verbose_name = 'Вложение занятия'
        verbose_name_plural = 'Вложения занятий'


class LiveLessonChatArchive(models.Model):
    """Снимок переписки, опубликованный для одного урока одной группы."""

    lesson = models.ForeignKey(
        LiveLesson, on_delete=models.PROTECT, related_name='chat_archives',
        verbose_name='Онлайн-занятие',
    )
    group = models.ForeignKey(
        'Course.LearnGroup', on_delete=models.PROTECT, related_name='live_chat_archives',
        verbose_name='Учебная группа',
    )
    schedule = models.ForeignKey(
        'Course.Schedule', on_delete=models.PROTECT, related_name='live_chat_archives',
        verbose_name='Урок программы',
    )
    file = models.FileField(
        storage=PrivateLiveLessonStorage(), upload_to=live_lesson_archive_upload_to,
        verbose_name='Файл истории чата',
    )
    last_message_id = models.PositiveBigIntegerField(verbose_name='Последнее сообщение в снимке')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='published_live_chat_archives', verbose_name='Сохранил',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Сохранено')

    class Meta:
        ordering = ('-created_at', '-pk')
        verbose_name = 'История чата онлайн-занятия'
        verbose_name_plural = 'Истории чата онлайн-занятий'
        indexes = [models.Index(fields=('group', 'schedule'), name='live_archive_group_lesson_idx')]
