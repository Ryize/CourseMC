from django.contrib import admin

from billing.models import InformationPayments, EducationCost


@admin.register(EducationCost)
class PersonAdmin(admin.ModelAdmin):
    fields = (
        'user',
        'amount',
    )
    list_display = (
        'user',
        'amount',
    )
    list_display_links = (
        'user',
        'amount',
    )
    list_filter = (
        'user',
        'amount',
    )
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8


@admin.register(InformationPayments)
class PersonAdmin(admin.ModelAdmin):
    fields = (
        'user',
        'amount',
        'datetime',
    )
    list_display = (
        'user',
        'amount',
        'datetime',
    )
    list_display_links = (
        'user',
        'amount',
        'datetime',
    )
    list_filter = (
        'user',
    )
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
