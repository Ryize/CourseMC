from django.db import migrations


PYRAMID_TITLES = {
    52: 'Задача «Пирамида». Начало',
    53: 'Задача «Пирамида». Продолжение',
    54: 'Задача «Пирамида». Завершение',
}


def rename_pyramid_lessons(apps, schema_editor):
    DirectionStudy = apps.get_model('Course', 'DirectionStudy')
    Schedule = apps.get_model('Course', 'Schedule')
    backend_direction = DirectionStudy.objects.filter(title='Backend 2024').first()
    if not backend_direction:
        return

    for position, theme in PYRAMID_TITLES.items():
        schedule = Schedule.objects.filter(
            direction_id=backend_direction.pk,
            position=position,
        ).first()
        if schedule and schedule.theme != theme:
            schedule.theme = theme
            schedule.save(update_fields=('theme',))


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0015_fix_decorator_assignment_example'),
    ]

    operations = [
        migrations.RunPython(rename_pyramid_lessons, migrations.RunPython.noop),
    ]
