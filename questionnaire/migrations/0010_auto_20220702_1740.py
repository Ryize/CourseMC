# Generated by Django 3.2.7 on 2022-07-02 17:40

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('questionnaire', '0009_passedpolls_useranswer'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='useranswer',
            name='answers',
        ),
        migrations.RemoveField(
            model_name='useranswer',
            name='question',
        ),
        migrations.AddField(
            model_name='useranswer',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
