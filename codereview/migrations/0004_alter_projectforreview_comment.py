# Generated by Django 3.2.7 on 2024-01-08 13:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codereview', '0003_alter_projectforreview_comment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectforreview',
            name='comment',
            field=models.TextField(default='Нет комментария', verbose_name='Комментарий ученика'),
        ),
    ]
