import hashlib

from django.contrib.auth import get_user
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views.generic import ListView

from Course.models import Student
from billing.models import InformationPayments, Absences, Adjustment
from billing.count_bill_logic import get_lesson_data


class BillingView(LoginRequiredMixin, ListView):
    """
    Выводит расписание курса на сайте.

    Расписания выводятся по модели Schedule, по 16 на странице.
    """

    model = InformationPayments
    template_name = 'billing/index.html'
    context_object_name = 'schedules'

    def get_context_data(self, *, object_list=None, **kwargs):
        """
        Добавляем кол-во отзывов, расписание.

        Для вывода кол-ва отзывов в шаблоне, передаём параметр reviews_count.
        Передаём список расписаний, отфильтрованных по дате.

        Args:
            object_list: стандартный параметр, не используется.
            kwargs: передаётся через super() в get_context_data

        Returns:
            dict: словарь с объектами моделей.
        """
        student = Student.objects.filter(name=get_user(self.request).username).first()
        student_email = get_student_email(self.request)
        billings = InformationPayments.objects.filter(
            user=student,
        ).order_by('-date').all()
        number_passes = 0
        if billings:
            last_billing = billings.first()
            number_passes = Absences.objects.filter(date__gte=last_billing.date, user=student).count()

        lesson_price, amount_classes, _ = get_lesson_data(self.request)

        cost_classes = get_cost_classes(self.request)

        return self._get_context(cost_classes, student_email, billings, amount_classes, number_passes, lesson_price,
                                 **kwargs)

    def _get_context(self, cost_classes, student_email, billings, amount_classes, number_passes, lesson_price,
                     **kwargs):
        context = super().get_context_data(**kwargs)
        context['cost_classes'] = cost_classes
        context['student_email'] = student_email
        context['amount_15_lesson'] = cost_classes // 50
        context['student_email'] = student_email
        context['billings'] = billings
        context['amount_classes'] = amount_classes
        context['number_passes'] = number_passes
        context['lesson_price'] = lesson_price
        return context

    def dispatch(self, request, *args, **kwargs):
        """
        Проверяем права на заход.

        Если пользователь не студент или не учиться, перекидываем на home.

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
        return super().dispatch(request, *args, **kwargs)

    def _get_param(self, name: str) -> str:
        """
        Проверяем права на заход.

        Если пользователь не студент или не учиться, перекидываем на home.

        Args:
            name: название параметра, который необходимо получить.

        Returns:
            str: значение из request.GET.
        """
        return self.request.GET.get(name)


def get_cost_classes(request):
    student = Student.objects.filter(name=get_user(request).username).first()
    billings = InformationPayments.objects.filter(
        user=student,
    ).order_by('-date').all()
    number_passes, sum_adjustments = 0, 0
    if billings:
        last_billing = billings.first()
        number_passes = Absences.objects.filter(date__gte=last_billing.date, user=student).count()
        adjustments = Adjustment.objects.filter(date__gte=last_billing.date, user=student).all()
        sum_adjustments = sum([i.amount for i in adjustments])

    lesson_price, amount_classes, cost_classes = get_lesson_data(request)

    cost_classes += -(number_passes * lesson_price) + sum_adjustments
    return cost_classes


def get_student_email(request):
    student = Student.objects.filter(name=get_user(request).username).first()
    return student.email


@login_required
def billing_success(request):
    amount = get_cost_classes(request)
    if amount == 0:
        return redirect('home')
    student = Student.objects.filter(name=request.user.username).first()
    InformationPayments.objects.create(user=student, amount=amount)
    return render(request, 'billing/success.html')


@login_required
def billing_fail(request):
    return render(request, 'billing/fail.html')
