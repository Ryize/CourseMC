from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from Course.models import Student


class InformationPayments(models.Model):
    user = models.ForeignKey(Student,
                             on_delete=models.PROTECT,
                             verbose_name="Ученик",
                             )
    amount = models.PositiveIntegerField(verbose_name='Сумма', default=0)
    datetime = models.DateTimeField(verbose_name='Дата', default=timezone.now)

    def __str__(self):
        return f'{self.user}, {self.amount}'

    class Meta:
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'


class EducationCost(models.Model):
    user = models.ForeignKey(Student,
                             on_delete=models.PROTECT,
                             verbose_name="Ученик",
                             )
    amount = models.PositiveIntegerField(verbose_name='Сумма', default=0)

    def __str__(self):
        return f'{self.user}, {self.amount}'

    class Meta:
        verbose_name = 'Размер оплаты'
        verbose_name_plural = 'Размеры оплат'
