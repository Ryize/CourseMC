"""Views для страниц связанных с оплатой."""
from typing import Iterable

from django.contrib.auth import get_user
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.views.generic import ListView

from Course.models import Student
from billing.check_billing import get_payment_url
from billing.models import (InformationPayments, Absences,
                            Adjustment, EducationCost, PaymentVerification)
from billing.count_bill_logic import get_lesson_data


class BillingView(LoginRequiredMixin, ListView):
    """
    Выводит список предыдущих платежей и реализует возможность оплаты.

    В качестве сервиса оплаты используется ЮКасса.
    """

    model = InformationPayments
    template_name = 'billing/index.html'
    context_object_name = 'schedules'

    def get_context_data(self, *, object_list=None, **kwargs) -> dict:
        """
        Добавляем кол-во уроков, пропусков, список предыдущих платежей
        и размер оплаты.

        Args:
            object_list: стандартный параметр, не используется.
            kwargs: передаётся через super() в get_context_data

        Returns:
            dict: словарь с параметрами.
        """
        student = Student.objects.filter(
            name=get_user(self.request).username,
        ).first()
        student_email = get_student_email(self.request)
        billings = InformationPayments.objects.filter(
            user=student,
        ).order_by('-date').all()
        number_passes = 0
        if billings:
            last_billing = billings.first()
            number_passes = Absences.objects.filter(
                date__gte=last_billing.date,
                user=student,
            ).count()

        lesson_price, amount_classes, _ = get_lesson_data(
            get_user(self.request),
        )

        cost_classes = get_cost_classes(get_user(self.request))

        return self._get_context(
            cost_classes,
            student_email,
            billings,
            amount_classes,
            number_passes,
            lesson_price,
            **kwargs
        )

    def _get_context(
            self,
            cost_classes: int,
            student_email: str,
            billings: Iterable,
            amount_classes: int,
            number_passes: int,
            lesson_price: int,
            **kwargs
    ) -> dict:
        context = super().get_context_data(**kwargs)
        context['cost_classes'] = cost_classes
        context['student_email'] = student_email
        context['amount_15_lesson'] = 1
        context['student_email'] = student_email
        context['billings'] = billings[::-1]
        context['amount_classes'] = amount_classes
        context['number_passes'] = number_passes
        context['lesson_price'] = lesson_price
        if cost_classes < 1:
            return context
        payment_data = get_payment_url(cost_classes)
        student = Student.objects.filter(
            name=get_user(self.request).username,
        ).first()
        PaymentVerification.objects.create(user=student,
                                           payment_id=payment_data[1],
                                           amount=cost_classes)
        context['payment_url'] = payment_data[0]
        return context

    def dispatch(self, request, *args, **kwargs):
        """
        Проверяем права на заход.

        Если пользователь не студент или не учиться, а также если нет размера
        оплаты в модели EducationCost, перенаправляем на главную страницу.

        Args:
            request: объект HTTP запроса.
            args: передаётся через super() в dispatch
            kwargs: передаётся через super() в dispatch

        Returns:
            bool: можно/нет зайти на страницу (через родительский dispatch).
        """
        student = Student.objects.filter(
            name=get_user(self.request).username, is_learned=True,
        ).first()
        if not student:
            return redirect('home')
        if not EducationCost.objects.filter(
                user__name=request.user.username,
        ).first():
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def _get_param(self, name: str) -> str:
        """
        Получаем данные из параметров запроса (GET).

        Args:
            name: str(название параметра, который необходимо получить).

        Returns:
            str: значение из request.GET.
        """
        return self.request.GET.get(name)


def get_cost_classes(user: User) -> int:
    """
    Получает размер оплаты для указанного пользователя.

    Args:
        user: AbstractUser (текущий пользователь)

    Returns:
        int (размер оплаты)
    """
    student = Student.objects.filter(
        name=user.username,
    ).first()
    billings = InformationPayments.objects.filter(
        user=student,
    ).order_by('-date').all()

    number_passes, sum_adjustments = 0, 0
    if billings:
        last_billing = billings.first()
        number_passes = Absences.objects.filter(
            date__gte=last_billing.date,
            user=student,
        ).count()
        adjustments = Adjustment.objects.filter(
            date__gte=last_billing.date,
            user=student,
        ).all()
        sum_adjustments = sum([i.amount for i in adjustments])

    lesson_price, amount_classes, cost_classes = get_lesson_data(user=user)

    cost_classes += int(
        -(number_passes * lesson_price * 0.75) + sum_adjustments)
    return cost_classes


def get_student_email(request) -> str:
    """
    Получает email текущего пользователя.

    Args:
        request: WSGIRequest (стандартный request,
            нужен для получения пользователя).

    Returns:
        str (строка с почтой пользователя)
    """
    student = Student.objects.filter(name=get_user(request).username).first()
    return student.email


@login_required
def billing_success(request):
    """
    Страница успешной оплаты.

    При заходе, автоматически добавляет платёж в InformationPayments.

    Args:
        request: WSGIRequest (стандартный request,
            нужен для получения пользователя).

    Returns:
        HttpResponse (HTML страница).
    """
    amount = get_cost_classes(get_user(request))
    if amount == 0:
        return redirect('home')
    student = Student.objects.filter(name=request.user.username).first()
    InformationPayments.objects.create(user=student, amount=amount)
    return render(request, 'billing/success.html')


@login_required
def billing_fail(request):
    """
    Страница неуспешной оплаты.

    Args:
        request: WSGIRequest (не используется).

    Returns:
        HttpResponse (HTML страница).
    """
    return render(request, 'billing/fail.html')
