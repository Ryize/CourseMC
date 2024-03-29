import calendar
import datetime

from django.contrib.auth.models import User

from Course.models import Student, ClassesTimetable
from billing.models import EducationCost, InformationPayments


def weekday_count(start: str, end: str) -> dict:
    """
    Считаем сколько уроков было за неделю.

    Args:
        start: str (дата начала)
        end: str (дата окончания)

    Returns:
        dict:
            key - Названия дня на русском языке
            value - Кол-во уроков в этот день
    """
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
    week_russian = {en: rus for en, rus in zip(
        weekdays_english, weekdays_russian
    )}
    for i in range((end_date - start_date).days):
        day = calendar.day_name[
            (start_date + datetime.timedelta(days=i + 1)).weekday()]
        week[week_russian[day]] = week.get(
            week_russian[day], 0) + 1 if week_russian[day] in week else 1
    return week


def get_lesson_data(user: User) -> tuple:
    """
    Получаем информацию об оплате пользователя.

    Args:
        user: User (стандартный Django пользователь)

    Returns:
        tuple:
            [0] - стоимость одного занятия
            [1] - кол-во прошедших занятий
            [2] - сколько должен за прошедшие занятия
    """

    lesson_price = EducationCost.objects.filter(
        user__name=user.username).first().amount
    last_pay = str(InformationPayments.objects.filter(
        user__name=user.username
    ).last().date).split()[0]
    current_date = str(datetime.datetime.now()).split()[0]
    dates = weekday_count(last_pay, current_date)
    student = Student.objects.filter(name=user.username).first()
    timetable = ClassesTimetable.objects.filter(group=student.groups).values(
        'weekday').all()
    weekdays = set(map(lambda i: i['weekday'], timetable))
    cost_classes = 0  # Сколько денег должен
    amount_occupations = 0  # Кол-во занятий
    for weekday in weekdays:
        if dates.get(weekday):
            cost_classes += dates[weekday] * lesson_price
            amount_occupations += dates[weekday]
    return lesson_price, amount_occupations, cost_classes
