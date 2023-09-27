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
    date = models.DateField(verbose_name='Дата', default=timezone.now)

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


class Absences(models.Model):
    user = models.ForeignKey(Student,
                             on_delete=models.PROTECT,
                             verbose_name="Ученик",
                             )
    date = models.DateField(verbose_name='Дата', default=timezone.now)

    def __str__(self):
        return f'{self.user}, {self.date}'

    class Meta:
        verbose_name = 'Пропуск'
        verbose_name_plural = 'Пропуски'


class Adjustment(models.Model):
    reasons = (
        ('Доп. занятие', 'Доп. занятие'),
        ('Индивидуальное занятие', 'Индивидуальное занятие'),
        ('Лекция', 'Лекция'),
        ('Пробное собеседование', 'Пробное собеседование'),
        ('Другое', 'Другое'),
    )
    user = models.ForeignKey(Student,
                             on_delete=models.PROTECT,
                             verbose_name="Ученик",
                             )
    reason = models.CharField(max_length=128, verbose_name="Причина", choices=reasons)
    amount = models.IntegerField(verbose_name="Сумма")
    date = models.DateField(verbose_name='Дата', default=timezone.now)

    def __str__(self):
        return f'{self.user}, {self.amount} ({self.reason})'

    class Meta:
        verbose_name = 'Корректировка'
        verbose_name_plural = 'Корректировки'
        