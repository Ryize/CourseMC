# Generated by Django 3.2.7 on 2022-07-25 17:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0012_alter_post_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="post",
            name="image",
            field=models.ImageField(
                default="https://biz.liga.net/all/all/article/mir-it-kak-otlichaetsya-zhizn-programmista-v-ukraine-i-za-rubezhom",
                upload_to="uploads/blog/%Y/%m/%d",
                verbose_name="Изображение",
            ),
        ),
    ]
