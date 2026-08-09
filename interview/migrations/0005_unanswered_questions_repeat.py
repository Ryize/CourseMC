from django.db import migrations, models


def mark_unrated_questions_for_repeat(apps, schema_editor):
    InterviewQuestionProgress = apps.get_model(
        'interview',
        'InterviewQuestionProgress',
    )
    InterviewQuestionProgress.objects.filter(status='unrated').update(status='repeat')


class Migration(migrations.Migration):

    dependencies = [
        ('interview', '0004_interviewquestionprogress'),
    ]

    operations = [
        migrations.AlterField(
            model_name='interviewquestionprogress',
            name='status',
            field=models.CharField(
                choices=[
                    ('unrated', 'Не оценен'),
                    ('answered', 'Ответил'),
                    ('repeat', 'Повторить'),
                ],
                default='repeat',
                max_length=16,
                verbose_name='Статус',
            ),
        ),
        migrations.RunPython(
            mark_unrated_questions_for_repeat,
            migrations.RunPython.noop,
        ),
    ]
