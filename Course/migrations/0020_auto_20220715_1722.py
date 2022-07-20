# Generated by Django 3.2.7 on 2022-07-15 14:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0019_auto_20220715_1643'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schedule',
            name='absent',
            field=models.ManyToManyField(blank=True, null=True, related_name='absents', to='Course.Student', verbose_name='Отсутствующие'),
        ),
        migrations.AlterField(
            model_name='student',
            name='password',
            field=models.CharField(default=3232, max_length=128, verbose_name='Пароль'),
        ),
    ]
