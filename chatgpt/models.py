from django.contrib.auth.models import User
from django.db import models
from django.utils.safestring import mark_safe


class RequestsGPT(models.Model):
    user = models.ForeignKey(User, verbose_name='Пользователь', on_delete=models.SET_NULL, null=True)
    text_request = models.TextField(verbose_name='Текст запроса')
    text_response = models.TextField(verbose_name='Текст ответа')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    def text_response_safe(self):
        return mark_safe(self.text_response)

    def text_request_safe(self):
        text = self.text_request
        text = text.replace(' ', '&nbsp;').replace('\n', '<br>').replace('\t', '    ')
        return mark_safe(text)

    def text_request_max_length(self):
        return mark_safe(self.text_request[:50])

    text_response_safe.short_description = 'Ответ'
    text_request_safe.short_description = 'Запрос'
    text_request_max_length.short_description = 'Текст запроса'

    def __str__(self):
        return f'{self.user}, {self.text_request}'

    class Meta:
        verbose_name = 'Запрос'
        verbose_name_plural = 'Запросы'
