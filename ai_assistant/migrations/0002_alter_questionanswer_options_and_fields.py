from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='questionanswer',
            options={
                'verbose_name': 'Вопрос и ответ',
                'verbose_name_plural': 'Вопросы и ответы',
            },
        ),
        migrations.AlterField(
            model_name='questionanswer',
            name='answer',
            field=models.TextField(verbose_name='Ответ'),
        ),
        migrations.AlterField(
            model_name='questionanswer',
            name='question',
            field=models.TextField(verbose_name='Вопрос'),
        ),
    ]
