from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('live_lessons', '0007_classroom_controls')]

    operations = [
        migrations.AlterField(
            model_name='livelesson', name='waiting_room_enabled',
            field=models.BooleanField(default=True, verbose_name='Зал ожидания'),
        ),
    ]
