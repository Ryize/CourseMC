# Generated by Django 3.2.7 on 2022-06-30 11:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('questionnaire', '0007_auto_20220630_1151'),
    ]

    operations = [
        migrations.AlterField(
            model_name='answerquestion',
            name='question',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='questionnaire.question', verbose_name='Вопрос'),
        ),
        migrations.AlterField(
            model_name='question',
            name='quiz',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='questionnaire.quiz', verbose_name='Опрос'),
        ),
    ]
