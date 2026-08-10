from collections import Counter

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def link_unambiguous_profiles(apps, schema_editor):
    Student = apps.get_model('Course', 'Student')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))

    name_counts = Counter(Student.objects.values_list('name', flat=True))
    users_by_username = {
        user.username: user.pk
        for user in User.objects.only('pk', 'username').iterator()
    }

    for student in Student.objects.only('pk', 'name').iterator():
        if name_counts[student.name] != 1:
            continue
        user_id = users_by_username.get(student.name)
        if user_id:
            Student.objects.filter(pk=student.pk).update(user_id=user_id)


def unlink_profiles(apps, schema_editor):
    Student = apps.get_model('Course', 'Student')
    Student.objects.update(user_id=None)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('Course', '0004_schedule_position_and_archive'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='user',
            field=models.OneToOneField(
                blank=True,
                help_text=(
                    'Основной аккаунт Django. Старые поля логина, почты и '
                    'пароля сохраняются временно для совместимости с ботом.'
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='course_profile',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Аккаунт',
            ),
        ),
        migrations.RunPython(link_unambiguous_profiles, unlink_profiles),
    ]
