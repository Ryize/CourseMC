# Generated by Django 3.2.7 on 2022-11-03 10:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0014_alter_post_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='description',
            field=models.CharField(max_length=512, verbose_name='Описание'),
        ),
    ]
