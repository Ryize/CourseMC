# Generated by Django 3.2.7 on 2022-07-09 12:38

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('questionnaire', '0011_auto_20220702_1742'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='passedpolls',
            options={'verbose_name': 'Пройденный опрос', 'verbose_name_plural': 'Пройденные опросы'},
        ),
        migrations.AlterField(
            model_name='passedpolls',
            name='passed_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь'),
        ),
        migrations.AlterField(
            model_name='quiz',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь'),
        ),
        migrations.AlterField(
            model_name='useranswer',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь'),
        ),
        migrations.CreateModel(
            name='Rating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answer_number', models.IntegerField(verbose_name='Число звёзд')),
                ('comment', models.CharField(blank=True, default='Комментарий не добавлен!', max_length=750)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rating', to='questionnaire.quiz', verbose_name='Опрос')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Рейтинг',
                'verbose_name_plural': 'Рейтинг',
            },
        ),
    ]
