from ckeditor_uploader.fields import RichTextUploadingField
from colorfield.fields import ColorField
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse_lazy


class Post(models.Model):
    title = models.CharField(max_length=122, verbose_name='Название')
    description = models.CharField(max_length=256, verbose_name='Описание')
    content = RichTextUploadingField(verbose_name='Текст поста', null=False)
    author = models.ForeignKey(User, on_delete=models.SET_DEFAULT, default='Пользователь удалён', verbose_name='Автор')
    image = models.ImageField(upload_to='uploads/blog/%Y/%m/%d',
                              default='uploads/blog/default.jpeg',
                              verbose_name='Изображение', null=False)
    is_displayed = models.BooleanField(default=False, verbose_name='Отображается')
    categories = models.ManyToManyField('Category', related_name='posts', verbose_name='Категории')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        verbose_name = 'Пост'
        verbose_name_plural = 'Посты'

    def get_absolute_url(self):
        return reverse_lazy('post_view', kwargs={'pk': self.pk})

    def __str__(self):
        return f'{self.title}, {self.author}'


class Comment(models.Model):
    comment = models.TextField(verbose_name='Комментарий')
    author = models.ForeignKey(User, on_delete=models.SET_DEFAULT, default='Пользователь удалён', verbose_name='Автор')
    post = models.ForeignKey('Post', on_delete=models.CASCADE, verbose_name='Пост')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Написан', null=True)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'

    def __str__(self):
        return f'{self.comment}, {self.post}'


class Category(models.Model):
    title = models.CharField(max_length=64, verbose_name='Название категории')
    color = ColorField(default='#FF0000', verbose_name='Цвет фона')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана', null=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return f'{self.title}'
