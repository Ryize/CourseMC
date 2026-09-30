import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('live_lessons', '0003_multi_group_open_lessons'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LiveLessonRemoval',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identity', models.CharField(max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name='removed_participants', to='live_lessons.livelesson')),
                ('removed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                 to=settings.AUTH_USER_MODEL)),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('lesson', 'identity'),
                                                               name='live_lesson_removal_once')]},
        ),
    ]
