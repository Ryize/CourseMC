from django.contrib import admin
from django.contrib.auth.models import User

from billing.models import InformationPayments, EducationCost, Absences, Adjustment
from billing.count_bill_logic import get_lesson_data


class UserListFilter(admin.SimpleListFilter):
    title = 'Пользователи'

    parameter_name = 'user'

    def lookups(self, request, model_admin):
        """
        Возвращает список кортежей.

        Первый элемент в каждом кортеже — это закодированное значение параметра,
        которое будет отображаться в URL-запросе.
        Второй элемент — это удобочитаемое имя параметра,
        которое появится на правой боковой панели.
        """
        students = set([chat.user for chat in InformationPayments.objects.all()])
        result_data = []
        for student in students:
            result_data.append((student.name, student.name,))
        return tuple(result_data)

    def queryset(self, request, queryset):
        """
        Возвращает отфильтрованный набор запросов на основе значения,
        указанного в строке запроса, которое можно получить с помощью
        `self.value()`.
        """
        if not self.value():
            return queryset
        return queryset.filter(user=User.objects.filter(username=self.value()).first())


@admin.register(EducationCost)
class EducationCostAdmin(admin.ModelAdmin):
    fields = (
        'user',
        'amount',
    )
    list_display = (
        'user',
        'amount',
        'should',
    )
    list_display_links = (
        'user',
        'amount',
        'should',
    )
    list_filter = (
        'user',
        'amount',
    )
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8

    def should(self, obj):
        user = User.objects.filter(username=obj.user.name).first()
        if user:
            last_pay = InformationPayments.objects.filter(
                user__name=user.username
            ).first()
            if last_pay:
                _, _, cost_classes = get_lesson_data(None, user=user)
                if cost_classes > 0:
                    return cost_classes

    should.short_description = 'Должен'
    should.empty_value_display = 'Оплатил'


@admin.register(InformationPayments)
class InformationPaymentsAdmin(admin.ModelAdmin):
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
class AbsencesAdmin(admin.ModelAdmin):
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
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8


@admin.register(Adjustment)
class AdjustmentAdmin(admin.ModelAdmin):
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
