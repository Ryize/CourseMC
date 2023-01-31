from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import F, Count

from chatgpt.models import RequestsGPT


class DecadeBornListFilter(admin.SimpleListFilter):
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
        users = set([chat.user for chat in RequestsGPT.objects.all()])
        result_data = []
        for user in users:
            result_data.append((user.username, user.username,))
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


@admin.register(RequestsGPT)
class RequestsGPTAdmin(admin.ModelAdmin):
    fields = (
        "user",
        "text_request_safe",
        "text_response_safe",
        "created_at",
    )
    list_display = (
        "user",
        "text_request_max_length",
        "created_at",
    )
    list_display_links = (
        "user",
        "text_request_max_length",
        "created_at",
    )
    readonly_fields = (
        "user",
        "text_request_safe",
        "text_response_safe",
        "created_at",
    )
    empty_value_display = "-пустой-"
    list_per_page = 64
    list_max_show_all = 8
    search_fields = (
        "user",
        "created_at",
    )
    list_filter = (DecadeBornListFilter,)
    date_hierarchy = "created_at"
