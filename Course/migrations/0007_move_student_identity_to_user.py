from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def move_student_emails(apps, schema_editor):
    """Сохраняет рабочий адрес профиля в каноническом аккаунте User."""
    Student = apps.get_model('Course', 'Student')
    for student in Student.objects.select_related('user').iterator():
        email = (student.email or '').strip()
        if email and student.user.email != email:
            student.user.email = email
            student.user.save(update_fields=('email',))


class Migration(migrations.Migration):
    dependencies = [
        ('Course', '0006_require_student_user'),
    ]

    operations = [
        migrations.RunPython(move_student_emails, migrations.RunPython.noop),
        migrations.RemoveField(model_name='student', name='email'),
        migrations.RemoveField(model_name='student', name='name'),
        migrations.RemoveField(model_name='student', name='password'),
        migrations.AlterField(
            model_name='student',
            name='user',
            field=models.OneToOneField(
                help_text='Единственный источник логина, почты и пароля ученика.',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='course_profile',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Аккаунт',
            ),
        ),
    ]
