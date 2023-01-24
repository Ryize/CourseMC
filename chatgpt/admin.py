from django.contrib import admin

from chatgpt.models import RequestsGPT


@admin.register(RequestsGPT)
class RequestsGPTAdmin(admin.ModelAdmin):
    fields = (
        "user",
        "text_request",
        "text_response",
        "created_at",
    )
    list_display = (
        "user",
        "text_request",
        "created_at",
    )
    list_display_links = (
        "user",
        "text_request",
        "created_at",
    )
    readonly_fields = (
        "user",
        "text_request",
        "text_response",
        "created_at",
    )
    empty_value_display = "-пустой-"
    list_per_page = 64
    list_max_show_all = 8
    search_fields = (
        "user",
        "created_at",
    )
    list_filter = ('user',)
    date_hierarchy = "created_at"
