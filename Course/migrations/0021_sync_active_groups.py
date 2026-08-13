from django.db import migrations


def sync_active_groups(apps, schema_editor):
    LearnGroup = apps.get_model('Course', 'LearnGroup')
    Student = apps.get_model('Course', 'Student')

    active_group_ids = set(
        Student.objects
        .filter(is_learned=True)
        .values_list('groups_id', flat=True)
    )
    LearnGroup.objects.filter(pk__in=active_group_ids).update(is_studies=True)
    LearnGroup.objects.exclude(pk__in=active_group_ids).update(is_studies=False)


class Migration(migrations.Migration):
    dependencies = [
        ('Course', '0020_alter_schedule_lesson_materials_alter_schedule_plan'),
    ]

    operations = [
        migrations.RunPython(sync_active_groups, migrations.RunPython.noop),
    ]
