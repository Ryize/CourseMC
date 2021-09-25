# Generated by Django 3.1.7 on 2021-09-20 13:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0005_auto_20210918_1105'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='schedule',
            options={'verbose_name': 'Расписание', 'verbose_name_plural': 'Расписания'},
        ),
        migrations.AlterField(
            model_name='student',
            name='email',
            field=models.EmailField(max_length=64, verbose_name='Почта'),
        ),
        migrations.AlterField(
            model_name='student',
            name='password',
            field=models.CharField(default=7750, max_length=128, verbose_name='Пароль'),
        ),
    ]
