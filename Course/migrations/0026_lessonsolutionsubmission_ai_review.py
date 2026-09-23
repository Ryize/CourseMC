from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('Course', '0025_studentcard_studentnote'),
    ]

    operations = [
        migrations.AddField(
            model_name='lessonsolutionsubmission',
            name='ai_status',
            field=models.CharField(choices=[('not_requested', 'Не проверялась'), ('pending', 'Проверяется'), ('ready', 'Рекомендация готова'), ('partial', 'Проверена часть файлов'), ('unsupported', 'Нет доступных для анализа файлов'), ('failed', 'Ошибка проверки')], default='not_requested', max_length=20, verbose_name='Проверка ИИ'),
        ),
        migrations.AddField(
            model_name='lessonsolutionsubmission',
            name='ai_feedback',
            field=models.TextField(blank=True, verbose_name='Рекомендация ИИ'),
        ),
        migrations.AddField(
            model_name='lessonsolutionsubmission',
            name='ai_issue_count',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Найдено проблем'),
        ),
        migrations.AddField(
            model_name='lessonsolutionsubmission',
            name='ai_source_summary',
            field=models.TextField(blank=True, verbose_name='Какие файлы проверены'),
        ),
        migrations.AddField(
            model_name='lessonsolutionsubmission',
            name='ai_error',
            field=models.CharField(blank=True, max_length=500, verbose_name='Ошибка проверки ИИ'),
        ),
        migrations.AddField(
            model_name='lessonsolutionsubmission',
            name='ai_model',
            field=models.CharField(blank=True, max_length=100, verbose_name='Модель ИИ'),
        ),
        migrations.AddField(
            model_name='lessonsolutionsubmission',
            name='ai_reviewed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Проверено ИИ'),
        ),
    ]
