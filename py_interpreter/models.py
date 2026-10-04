from django.db import models
from django.conf import settings
from django.utils import timezone


class SharedCodeDocument(models.Model):
    lesson = models.OneToOneField('live_lessons.LiveLesson', on_delete=models.CASCADE,
                                 related_name='shared_code')
    state = models.BinaryField()
    code = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(default=timezone.now)


class SharedCodeParticipant(models.Model):
    document = models.ForeignKey(SharedCodeDocument, on_delete=models.CASCADE, related_name='editors')
    identity = models.CharField(max_length=128)
    name = models.CharField(max_length=160)
    can_edit = models.BooleanField(default=False)
    cursor = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('document', 'identity'), name='shared_code_identity_once')]


class SharedCodeSnapshot(models.Model):
    document = models.ForeignKey(SharedCodeDocument, on_delete=models.CASCADE, related_name='snapshots')
    title = models.CharField(max_length=100, default='Код занятия')
    code = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')


class SharedCodeAttachment(models.Model):
    """Publish an immutable Python version to a curriculum lesson for one group."""
    snapshot = models.ForeignKey(SharedCodeSnapshot, on_delete=models.PROTECT, related_name='attachments')
    group = models.ForeignKey('Course.LearnGroup', on_delete=models.PROTECT, related_name='shared_code_files')
    schedule = models.ForeignKey('Course.Schedule', on_delete=models.PROTECT, related_name='shared_code_files')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        constraints = [models.UniqueConstraint(fields=('snapshot', 'group', 'schedule'),
                                               name='shared_code_file_once')]
