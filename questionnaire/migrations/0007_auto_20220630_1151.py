# Generated by Django 3.2.7 on 2022-06-30 11:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('questionnaire', '0006_alter_quiz_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='answerquestion',
            name='correct',
            field=models.BooleanField(default=False, verbose_name='Это правильный ответ?'),
        ),
        migrations.AlterField(
            model_name='answerquestion',
            name='question',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='questionnaire.question', verbose_name='Вопрос'),
        ),
        migrations.AlterField(
            model_name='question',
            name='quiz',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quiz', to='questionnaire.quiz', verbose_name='Опрос'),
        ),
    ]
