import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('live_lessons', '0002_livelessonmessage_livelessonattachment_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='livelesson',
            name='group',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='live_lessons', to='Course.learngroup', verbose_name='Учебная группа',
            ),
        ),
        migrations.AddField(
            model_name='livelesson',
            name='additional_groups',
            field=models.ManyToManyField(
                blank=True, related_name='additional_live_lessons',
                to='Course.learngroup', verbose_name='Дополнительные группы',
            ),
        ),
        migrations.AddField(
            model_name='livelesson',
            name='audience',
            field=models.CharField(
                choices=[('groups', 'Выбранные группы'), ('open', 'Любой по ссылке')],
                default='groups', max_length=8, verbose_name='Кому доступно',
            ),
        ),
        migrations.AlterField(
            model_name='livelessonmessage',
            name='author',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='live_lesson_messages', to=settings.AUTH_USER_MODEL, verbose_name='Автор',
            ),
        ),
        migrations.AddField(
            model_name='livelessonmessage',
            name='guest_id',
            field=models.UUIDField(blank=True, null=True, verbose_name='Идентификатор гостя'),
        ),
        migrations.AddField(
            model_name='livelessonmessage',
            name='guest_name',
            field=models.CharField(blank=True, max_length=40, verbose_name='Имя гостя'),
        ),
        migrations.AddConstraint(
            model_name='livelessonmessage',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(author__isnull=False, guest_id__isnull=True, guest_name='') |
                    (models.Q(author__isnull=True, guest_id__isnull=False) & ~models.Q(guest_name=''))
                ),
                name='live_chat_one_author',
            ),
        ),
        migrations.AddIndex(
            model_name='livelessonmessage',
            index=models.Index(fields=['lesson', 'guest_id', 'created_at'], name='live_chat_guest_rate_idx'),
        ),
    ]
