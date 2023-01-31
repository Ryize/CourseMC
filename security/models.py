from django.contrib.auth.models import User
from django.db import models


class IPVisitors(models.Model):
    user = models.ForeignKey(User,
                             on_delete=models.SET_NULL,
                             verbose_name='Пользователь',
                             related_name='ip',
                             null=True)
    ip = models.GenericIPAddressField(verbose_name='IP')

    def __str__(self):
        return self.ip

    class Meta:
        verbose_name = 'Сессия'
        verbose_name_plural = 'Все сессии'


class BlockedIPAddress(models.Model):
    ip = models.GenericIPAddressField(verbose_name='Заблокированный IP')

    def __str__(self):
        return self.ip

    class Meta:
        verbose_name = 'Заблокированный IP'
        verbose_name_plural = 'Заблокированные IP'
