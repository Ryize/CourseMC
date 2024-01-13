from typing import Optional

from django.db.models import IntegerField, Case, Value, When
from django.contrib import admin
from django.contrib.auth.models import User

from billing.models import (Absences, Adjustment,
                            EducationCost, InformationPayments)
from billing.views import get_cost_classes
from Course.models import ClassesTimetable, Student


class OnlyMyStudentMixin:
    """
    Позволяет получать в поле user (ForeignKey связанное со Student) только
    своих студентов и которых идут занятия
    """

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user" and not request.user.is_superuser:
            teacher = Student.objects.filter(
                name=request.user.username).first()
            kwargs["queryset"] = Student.objects.filter(is_learned=True,
                                                        groups__teacher=teacher).order_by(
                '-pk')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(
                user__groups__teacher__name=request.user.username)
        return queryset


class UserListFilter(admin.SimpleListFilter):
    """
    Фильтр для пользователей в админ-панели списка платежей
    (InformationPaymentsAdmin).

    Позволяет добавлять в стандартный фильтр только тех, кто оплатил хотя бы
    раз.
    """

    title = 'Ученики'

    parameter_name = 'user'

    def lookups(self, request, model_admin) -> tuple:
        """
        Возвращает список кортежей.

        Returns:
            tuple:
            [i][0] - закодированное значение параметра, которое будет
            отображаться в URL-запросе.
            [i][1] - удобочитаемое имя параметра, которое появится на правой
            боковой панели.
        """
        students = set(
            [chat.user for chat in InformationPayments.objects.all() if
             chat.user.is_learned])
        result_data = []
        for student in students:
            result_data.append((student.name, student.name,))
        return tuple(result_data)

    def queryset(self, request, queryset):
        """
        Фильтрует запрос.

        Returns:
            queryset: Отфильтрованный набор запросов на основе значения,
            указанного в строке запроса, которое можно получить с помощью
            `self.value()`.
        """
        if not self.value():
            return queryset
        user = Student.objects.filter(name=self.value()).first()
        return queryset.filter(user=user)


@admin.register(EducationCost)
class EducationCostAdmin(OnlyMyStudentMixin, admin.ModelAdmin):
    """
    Стоимость обучения.

    Помимо стандартных полей из models, содержит кастомные
    поля определённые в этом классе.
    Используется как мониторинг должников/подсчёта общей прибыли за месяц.
    """
    fields = (
        'user',
        'amount',
    )
    list_display = (
        'user',
        'amount',
        'per_month',
        'debt',
    )
    list_display_links = (
        'user',
        'amount',
        'per_month',
        'debt',
    )
    list_filter = (
        'amount',
        UserListFilter,
    )
    actions = ('calculate_amount', 'calculate_taking_account_risks',)
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8

    def _get_debt(self, obj):
        """
           Сколько ученик должен денег.

           Если ученика не существует, или сумма равна или меньше 0,
           возвращает None. Иначе возвращает сумму долга.
        """
        user = User.objects.filter(username=obj.user.name).first()
        if user:
            last_pay = InformationPayments.objects.filter(
                user__name=user.username
            ).first()
            if not last_pay:
                return

            cost_classes = get_cost_classes(user)
            if cost_classes > 0:
                return cost_classes

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if not request.user.is_superuser:
            queryset = queryset.filter(
                user__groups__teacher__name=request.user.username)

        # Значения debt из _get_data для каждой записи
        debt_values_list = [self._get_debt(obj) for obj in queryset]

        # Список условий для каждой записи
        conditions = [
            When(id=obj.id, then=Value(
                debt_value, output_field=IntegerField()))
            for obj, debt_value in zip(queryset, debt_values_list)]

        # Case и annotate для присвоения значений debt
        queryset = queryset.annotate(
            debt=Case(
                *conditions,
                default=Value(
                    0,
                    output_field=IntegerField()
                ), output_field=IntegerField()
            )
        )

        return queryset.order_by('-debt')

    def debt(self, obj) -> Optional[int]:
        return obj.debt

    def per_month(self, obj) -> Optional[int]:
        """
        Сколько платит ученик за месяц.

        Если ученика нет, вернёт None. Иначе вернёт сумму оплаты за месяц.
        """
        student = Student.objects.filter(name=obj.user.name).first()
        group = student.groups
        if student:
            cost_one_lesson = EducationCost.objects.filter(
                user=student).first()
            number_classes = ClassesTimetable.objects.filter(
                group=group).count()
            return cost_one_lesson.amount * number_classes * 4

    def calculate_amount(self, request, queryset):
        """
        Действие из выпадающего меню для подсчета общей суммы оплаты за месяц
        для указанного числа учеников.
        """
        costs = self._calculate_amount_month(queryset)
        self.message_user(request, f'Итоговая сумма: {costs} рублей')

    def calculate_taking_account_risks(self, request, queryset):
        """
        Действие из выпадающего меню для подсчета общей суммы оплаты за месяц
        с учётом рисков (вычитает 10% от итоговой суммы).
        Риск это пропуск, отмена урока.
        """
        costs = self._calculate_amount_month(queryset)
        self.message_user(request,
                          f'Сумма с учётом рисков: {int(costs * 0.85)} рублей')

    @staticmethod
    def _calculate_amount_month(queryset) -> int:
        """
        Вспомогательный метод для подсчета суммы оплаты за месяц обучения.

        Необходимые данные передаются в Queryset.
        """
        costs = 0
        for cost in queryset.all():
            student = cost.user
            group = student.groups
            number_classes = ClassesTimetable.objects.filter(
                group=group).count()
            costs += cost.amount * number_classes * 4
        return costs

    calculate_amount.short_description = "Посчитать"
    calculate_taking_account_risks.short_description = ("Посчитать "
                                                        "с учётом рисков")

    debt.admin_order_field = 'debt'
    debt.short_description = 'Должен'
    debt.empty_value_display = 'Оплатил'

    per_month.short_description = 'За месяц'
    per_month.empty_value_display = 'Нет информации'


@admin.register(InformationPayments)
class InformationPaymentsAdmin(OnlyMyStudentMixin, admin.ModelAdmin):
    """
    Список платежей.

    Платёж может добавляться и через API.
    """
    fields = (
        'user',
        'amount',
        'date',
    )
    list_display = (
        'user',
        'amount',
        'date',
    )
    list_display_links = (
        'user',
        'amount',
        'date',
    )
    list_filter = (UserListFilter,)
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8


@admin.register(Absences)
class AbsencesAdmin(OnlyMyStudentMixin, admin.ModelAdmin):
    """
    Админ-панель для пропусков уроков.

    Пропуск может добавляться и через API.
    """
    fields = (
        'user',
        'date',
    )
    list_display = (
        'user',
        'date',
    )
    list_display_links = (
        'user',
        'date',
    )
    list_filter = (
        UserListFilter,
    )
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8


@admin.register(Adjustment)
class AdjustmentAdmin(OnlyMyStudentMixin, admin.ModelAdmin):
    """
    Админ-панель для корректировок оплаты.

    Корректировка может быть как с плюсом, так и с минусом.
    """
    fields = (
        'user',
        'reason',
        'amount',
        'date',
    )
    list_display = (
        'user',
        'reason',
        'amount',
        'date',
    )
    list_display_links = (
        'user',
        'reason',
        'amount',
        'date',
    )
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
