# Generated by Django 3.2.7 on 2022-07-20 11:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Course', '0021_auto_20220719_1307'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentquestion',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, verbose_name='Задан'),
        ),
        migrations.AlterField(
            model_name='student',
            name='password',
            field=models.CharField(default=1170, max_length=128, verbose_name='Пароль'),
        ),
    ]
