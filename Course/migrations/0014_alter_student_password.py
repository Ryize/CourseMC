# Generated by Django 3.2.7 on 2021-09-27 13:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Course", "0013_alter_student_password"),
    ]

    operations = [
        migrations.AlterField(
            model_name="student",
            name="password",
            field=models.CharField(default=9774, max_length=128, verbose_name="Пароль"),
        ),
    ]
