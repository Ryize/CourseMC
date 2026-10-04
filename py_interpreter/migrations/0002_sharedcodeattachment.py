import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('py_interpreter', '0001_initial'),
        ('Course', '0027_clean_lesson_solution_ai_feedback'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SharedCodeAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                               to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                           related_name='shared_code_files', to='Course.learngroup')),
                ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name='shared_code_files', to='Course.schedule')),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name='attachments', to='py_interpreter.sharedcodesnapshot')),
            ],
            options={
                'ordering': ('-created_at', '-pk'),
                'constraints': [models.UniqueConstraint(fields=('snapshot', 'group', 'schedule'),
                                                        name='shared_code_file_once')],
            },
        ),
    ]
