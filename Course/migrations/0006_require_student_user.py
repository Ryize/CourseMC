from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def ensure_every_profile_has_user(apps, schema_editor):
    Student = apps.get_model('Course', 'Student')
    missing_ids = list(
        Student.objects
        .filter(user_id__isnull=True)
        .order_by('pk')
        .values_list('pk', flat=True)[:10]
    )
    if missing_ids:
        raise RuntimeError(
            'Нельзя сделать Student.user обязательным: найдены профили без '
            f'аккаунта (первые ID: {missing_ids}).'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('Course', '0005_student_user_link'),
    ]

    operations = [
        migrations.RunPython(
            ensure_every_profile_has_user,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='student',
            name='user',
            field=models.OneToOneField(
                help_text=(
                    'Основной аккаунт Django. Старые поля логина, почты и '
                    'пароля сохраняются временно для совместимости с ботом.'
                ),
                on_delete=django.db.models.deletion.PROTECT,
                related_name='course_profile',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Аккаунт',
            ),
        ),
    ]
