from django.db import migrations, models


def fill_schedule_positions(apps, schema_editor):
    Schedule = apps.get_model('Course', 'Schedule')
    direction_ids = (
        Schedule.objects.order_by()
        .values_list('direction_id', flat=True)
        .distinct()
    )
    for direction_id in direction_ids:
        schedules = Schedule.objects.filter(direction_id=direction_id).order_by('pk')
        for position, schedule in enumerate(schedules, start=1):
            Schedule.objects.filter(pk=schedule.pk).update(position=position)


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0003_lesson_solutions'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='is_archived',
            field=models.BooleanField(
                default=False,
                help_text='Архивный урок не показывается ученикам и не удаляет их работы.',
                verbose_name='В архиве',
            ),
        ),
        migrations.AddField(
            model_name='schedule',
            name='position',
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text='Назначается автоматически. Изменяйте порядок через админку.',
                verbose_name='Порядок в программе',
            ),
        ),
        migrations.RunPython(fill_schedule_positions, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name='schedule',
            options={
                'ordering': ('direction_id', 'position', 'pk'),
                'verbose_name': 'Расписание',
                'verbose_name_plural': 'Расписания',
            },
        ),
        migrations.AddIndex(
            model_name='schedule',
            index=models.Index(
                fields=['direction', 'position'],
                name='course_sched_dir_pos_idx',
            ),
        ),
    ]
