from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import Course.models


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0002_enforce_schedule_plan'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LessonSolution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'На проверке'), ('accepted', 'Принято'), ('needs_revision', 'Нужна доработка')], default='pending', max_length=20, verbose_name='Статус проверки')),
                ('teacher_comment', models.TextField(blank=True, verbose_name='Комментарий преподавателя')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Проверено')),
                ('submitted_at', models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_lesson_solutions', to=settings.AUTH_USER_MODEL, verbose_name='Проверил')),
                ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='solutions', to='Course.schedule', verbose_name='Урок')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lesson_solutions', to='Course.student', verbose_name='Ученик')),
            ],
            options={
                'verbose_name': 'Решение урока',
                'verbose_name_plural': 'Решения уроков',
                'ordering': ('status', '-updated_at'),
            },
        ),
        migrations.CreateModel(
            name='LessonSolutionFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(storage=Course.models.PrivateLessonSolutionStorage(), upload_to=Course.models.lesson_solution_upload_to, verbose_name='Файл')),
                ('original_name', models.CharField(max_length=255, verbose_name='Имя файла')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Загружен')),
                ('solution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='Course.lessonsolution', verbose_name='Решение урока')),
            ],
            options={
                'verbose_name': 'Файл решения',
                'verbose_name_plural': 'Файлы решений',
                'ordering': ('uploaded_at',),
            },
        ),
        migrations.AddConstraint(
            model_name='lessonsolution',
            constraint=models.UniqueConstraint(fields=('schedule', 'student'), name='one_solution_per_lesson_and_student'),
        ),
    ]
