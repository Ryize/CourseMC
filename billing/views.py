import calendar
import datetime
import hashlib

from django.contrib.auth import get_user
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views.generic import ListView
from django.http import HttpRequest

from Course.models import Student, LearnGroup, ClassesTimetable
from billing.models import InformationPayments, EducationCost
from billing.count_bill_logic import get_lesson_data


class BillingView(LoginRequiredMixin, ListView):
    """
    Выводит расписание курса на сайте.

    Расписания выводятся по модели Schedule, по 16 на странице.
    """

    model = InformationPayments
    template_name = 'billing/index.html'
    context_object_name = 'schedules'
    paginate_by = 16

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
        context = super().get_context_data(**kwargs)
        student = Student.objects.filter(name=get_user(self.request).username).first()
        billings = InformationPayments.objects.filter(
            user=student,
        ).order_by('-datetime').all()
        context['billings'] = billings
        merchant_id = '28649'
        secret_word = '.d36f=0&s7?QX-a'
        order_id = f'{get_user(self.request).pk}'

        lesson_price, amount_classes, cost_classes = get_lesson_data(self.request)

        order_amount = f'{cost_classes}'
        currency = 'RUB'
        sign = hashlib.md5(
            f'{merchant_id}:{order_amount}:{secret_word}:{currency}:{order_id}'.encode('utf-8')).hexdigest()
        context['m'] = merchant_id
        context['oa'] = order_amount
        context['o'] = order_id
        context['s'] = sign
        context['currency'] = currency
        context['lesson_price'] = lesson_price
        context['amount_classes'] = amount_classes
        context['us_pk'] = get_user(self.request).pk
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
        # student = Student.objects.filter(
        #     name=get_user(self.request).username, is_learned=True,
        # ).first()
        # if not student:
        #     return redirect('home')
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


@login_required
def billing_success(request):
    _, _, amount = get_lesson_data(request)
    if amount == 0:
        return redirect('home')
    student = Student.objects.filter(name=request.user.username).first()
    InformationPayments.objects.create(user=student, amount=amount)
    return render(request, 'billing/success.html')


@login_required
def billing_fail(request):
    return render(request, 'billing/fail.html')
