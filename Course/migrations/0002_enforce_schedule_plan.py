from django.db import migrations, models


def fill_missing_plans(apps, schema_editor):
    schedule = apps.get_model('Course', 'Schedule')
    schedule.objects.filter(plan__isnull=True).update(
        plan='План не указан!',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            fill_missing_plans,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='schedule',
            name='plan',
            field=models.TextField(
                default='План не указан!',
                verbose_name='План урока',
            ),
        ),
    ]
