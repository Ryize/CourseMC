from django.contrib.auth.models import User
from django.db import models


class RequestsGPT(models.Model):
    user = models.ForeignKey(User, verbose_name='Пользователь', on_delete=models.SET_NULL, null=True)
    text_request = models.TextField(verbose_name='Текст запроса')
    text_response = models.TextField(verbose_name='Текст ответа')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    def __str__(self):
        return f'{self.user}, {self.text_request}'

    class Meta:
        verbose_name = 'Запрос'
        verbose_name_plural = 'Запросы'
