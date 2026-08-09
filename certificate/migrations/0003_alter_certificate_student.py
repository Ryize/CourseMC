from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('certificate', '0002_alter_certificate_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='certificate',
            name='student',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                to='Course.student',
                verbose_name='Студент',
            ),
        ),
    ]
