from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe

from certificate.models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    change_list_template = "admin/model_change_list.html"
    fields = (
        "student",
        "fio",
        "date",
        "comment",
        "number",
    )
    list_display = (
        "student",
        "date",
    )
    list_display_links = (
        "student",
        "date",
    )
    empty_value_display = "-пустой-"
    list_per_page = 64
    list_max_show_all = 8
    search_fields = (
        "comment",
    )
    readonly_fields = ('number',)
    date_hierarchy = "date"
