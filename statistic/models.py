from django.db import models

from Course.models import Student


class Payment(models.Model):
    """
    Модель для хранения данных по прибыли и ученикам, которые её приносят.
    """
    profit = models.PositiveIntegerField(verbose_name='Прибыль')
    students = models.ManyToManyField(Student, related_name='active_students')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата')

    def __str__(self):
        return f'Прибыль на {self.created_at}: {self.profit}'

    class Meta:
        verbose_name = 'Прибыль'
        verbose_name_plural = 'Прибыль'
