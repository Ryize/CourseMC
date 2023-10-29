import datetime

from django.db import models

from Course.models import Student


class Certificate(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT,
                                verbose_name='Студент', unique=True)
    date = models.DateField(default=datetime.datetime.now)
    number = models.PositiveIntegerField(verbose_name='Номер')

    def __str__(self):
        return f'{self.student}, {self.number}'

    class Meta:
        verbose_name = 'Сертификат'
        verbose_name_plural = 'Сертификаты'
