# Generated by Django 3.2.7 on 2022-07-15 13:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0018_auto_20220709_1538'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schedule',
            name='group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='Course.learngroup', verbose_name='Группа обучения'),
        ),
        migrations.AlterField(
            model_name='student',
            name='groups',
            field=models.ForeignKey(default=2, on_delete=django.db.models.deletion.CASCADE, related_name='students', to='Course.learngroup', verbose_name='Группа обучения'),
        ),
        migrations.AlterField(
            model_name='student',
            name='password',
            field=models.CharField(default=6385, max_length=128, verbose_name='Пароль'),
        ),
        migrations.AlterField(
            model_name='teacher',
            name='groups',
            field=models.ManyToManyField(related_name='teachers', to='Course.LearnGroup', verbose_name='Группы'),
        ),
    ]