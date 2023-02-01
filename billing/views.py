import calendar
import datetime
import hashlib

from django.contrib.auth import get_user
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import ListView

from Course.models import Student, LearnGroup, ClassesTimetable
from billing.models import InformationPayments, EducationCost


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
        ).all()
        context['billings'] = billings
        merchant_id = ''
        secret_word = ''
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


def weekday_count(start, end):
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d')
    week = {}
    weekdays_russian = ('Понедельник',
                        'Вторник',
                        'Среда',
                        'Четверг',
                        'Пятница',
                        'Суббота',
                        'Воскресенье',
                        )
    weekdays_english = ('Monday',
                        'Tuesday',
                        'Wednesday',
                        'Thursday',
                        'Friday',
                        'Saturday',
                        'Sunday',
                        )
    week_russian = {en: rus for en, rus in zip(weekdays_english, weekdays_russian)}
    for i in range((end_date - start_date).days):
        day = calendar.day_name[(start_date + datetime.timedelta(days=i + 1)).weekday()]
        week[week_russian[day]] = week[day] + 1 if day in week else 1
    return week


def get_lesson_data(request):
    lesson_price = EducationCost.objects.filter(user__name=get_user(request).username).first().amount
    last_pay = str(InformationPayments.objects.filter(
        user__name=get_user(request).username
    ).last().datetime).split()[0]
    current_date = str(datetime.datetime.now()).split()[0]
    dates = weekday_count(last_pay, current_date)
    student = Student.objects.filter(name=get_user(request).username).first()
    timetable = ClassesTimetable.objects.filter(group=student.groups).values('weekday').all()
    weekdays = set(map(lambda i: i['weekday'], timetable))
    cost_classes = 0
    amount_occupations = 0
    for weekday in weekdays:
        if dates.get(weekday):
            cost_classes += dates[weekday] * lesson_price
            amount_occupations += dates[weekday]
    return lesson_price, amount_occupations, cost_classes
