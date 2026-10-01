from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import migrations, models


def remember_schedule_dates(apps, schema_editor):
    Lesson = apps.get_model('live_lessons', 'LiveLesson')
    Reschedule = apps.get_model('live_lessons', 'LiveLessonReschedule')
    school_timezone = ZoneInfo(settings.TIME_ZONE)
    seen = set()
    for lesson in Lesson.objects.using(schema_editor.connection.alias).filter(
        timetable_slot__isnull=False,
    ).order_by('pk').iterator():
        first_move = Reschedule.objects.using(schema_editor.connection.alias).filter(
            lesson_id=lesson.pk,
        ).order_by('created_at', 'pk').first()
        source = first_move.old_scheduled_at if first_move else lesson.scheduled_at
        day = source.astimezone(school_timezone).date()
        key = (lesson.timetable_slot_id, day)
        # Старые дубли не удаляем. Один из них резервирует исходный день графика.
        if key not in seen:
            Lesson.objects.using(schema_editor.connection.alias).filter(pk=lesson.pk).update(timetable_date=day)
            seen.add(key)


class Migration(migrations.Migration):
    dependencies = [('live_lessons', '0005_livelessonchatarchive')]

    operations = [
        migrations.AddField(
            model_name='livelesson', name='timetable_date',
            field=models.DateField(blank=True, editable=False, null=True, verbose_name='Исходный день графика'),
        ),
        migrations.AddField(
            model_name='livelesson', name='room_cleanup_pending',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.RunPython(remember_schedule_dates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='livelesson',
            constraint=models.UniqueConstraint(fields=('timetable_slot', 'timetable_date'), name='live_slot_date_once'),
        ),
    ]
