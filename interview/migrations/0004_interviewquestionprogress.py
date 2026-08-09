from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('interview', '0003_interviewquestion_complexity'),
    ]

    operations = [
        migrations.CreateModel(
            name='InterviewQuestionProgress',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('unrated', 'Не оценен'),
                            ('answered', 'Ответил'),
                            ('repeat', 'Повторить'),
                        ],
                        default='unrated',
                        max_length=16,
                        verbose_name='Статус',
                    ),
                ),
                ('last_shown_at', models.DateTimeField(verbose_name='Последний показ')),
                (
                    'next_available_at',
                    models.DateTimeField(
                        db_index=True,
                        verbose_name='Можно показать снова',
                    ),
                ),
                ('shown_count', models.PositiveIntegerField(default=1, verbose_name='Показов')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлён')),
                (
                    'question',
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name='progress_entries',
                        to='interview.interviewquestion',
                        verbose_name='Вопрос',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name='interview_question_progress',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Пользователь',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Прогресс вопроса собеседования',
                'verbose_name_plural': 'Прогресс вопросов собеседования',
            },
        ),
        migrations.AddConstraint(
            model_name='interviewquestionprogress',
            constraint=models.UniqueConstraint(
                fields=('user', 'question'),
                name='interview_progress_user_question_uniq',
            ),
        ),
        migrations.AddIndex(
            model_name='interviewquestionprogress',
            index=models.Index(
                fields=['user', 'status', 'next_available_at'],
                name='intrv_prog_user_stat_idx',
            ),
        ),
    ]
