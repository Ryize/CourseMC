from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from Course.models import Student


class InformationPayments(models.Model):
    """
    Содержит информацию о оплате.

    Fields:
        user: ForeignKey (связь с пользователем, модель Student)
        amount: PositiveIntegerField (сумма оплаты. Всегда положительное число)
        date: DateField (дата оплаты)
    """
    user = models.ForeignKey(Student,
                             on_delete=models.PROTECT,
                             verbose_name='Ученик',
                             )
    amount = models.PositiveIntegerField(verbose_name='Сумма', default=0)
    date = models.DateField(verbose_name='Дата', default=timezone.now)

    def __str__(self):
        return f'{self.user}, {self.amount}'

    class Meta:
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'


class EducationCost(models.Model):
    """
    Сумма оплаты для конкретного ученика за один урок.

    Fields:
        user: ForeignKey (связь с пользователем, модель Student)
        amount: PositiveIntegerField (сумма оплаты. Всегда положительное число)
    """

    user = models.ForeignKey(Student,
                             on_delete=models.PROTECT,
                             verbose_name='Ученик',
                             )
    amount = models.PositiveIntegerField(verbose_name='Сумма', default=0)

    def __str__(self):
        return f'{self.user}, {self.amount}'

    class Meta:
        verbose_name = 'Размер оплаты'
        verbose_name_plural = 'Размеры оплат'


class Absences(models.Model):
    """
    Пропуск занятия. Оплата за пропуск идёт в размере 25%.

    Fields:
        user: ForeignKey (связь с пользователем, модель Student)
        date: DateField (дата пропуска)
    """
    user = models.ForeignKey(Student,
                             on_delete=models.PROTECT,
                             verbose_name='Ученик',
                             )
    date = models.DateField(verbose_name='Дата', default=timezone.now)

    def __str__(self):
        return f'{self.user}, {self.date}'

    class Meta:
        verbose_name = 'Пропуск'
        verbose_name_plural = 'Пропуски'


class Adjustment(models.Model):
    """
    Корректировка размера оплаты. Например в случае доп. урока.

    Fields:
        user: ForeignKey (связь с пользователем, модель Student)
        reason: CharField (причина пропуска. Выбор из уже заготовленных)
        amount: PositiveIntegerField (сумма оплаты)
        date: DateField (дата корректировки)
    """

    reasons = (
        ('Доп. занятие', 'Доп. занятие'),
        ('Индивидуальное занятие', 'Индивидуальное занятие'),
        ('Лекция', 'Лекция'),
        ('Пробное собеседование', 'Пробное собеседование'),
        ('Другое', 'Другое'),
    )
    user = models.ForeignKey(Student,
                             on_delete=models.PROTECT,
                             verbose_name='Ученик',
                             )
    reason = models.CharField(max_length=128, verbose_name='Причина',
                              choices=reasons)
    amount = models.IntegerField(verbose_name='Сумма')
    date = models.DateField(verbose_name='Дата', default=timezone.now)

    def __str__(self):
        return f'{self.user}, {self.amount} ({self.reason})'

    class Meta:
        verbose_name = 'Корректировка'
        verbose_name_plural = 'Корректировки'


class PaymentVerification(models.Model):
    """
    Содержит данные для проверки объекта через YooKassa.

    Fields:
        user: ForeignKey (связь с пользователем, модель Student)
        payment_id: CharField (id платежа. Получаем и используем в YooKassa)
        amount: PositiveIntegerField (сумма оплаты)
        date: DateTimeField (дата создания платежа)
    """
    user = models.ForeignKey(Student,
                             on_delete=models.CASCADE,
                             verbose_name='Ученик',
                             )

    payment_id = models.CharField(max_length=32, verbose_name='id платежа')

    amount = models.PositiveIntegerField()

    date = models.DateTimeField(verbose_name='Дата', default=timezone.now)
