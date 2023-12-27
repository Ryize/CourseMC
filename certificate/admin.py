import os

from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import redirect
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
        'download_cert',
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

    def download_cert(self, obj: Certificate):
        """
        Сколько платит ученик за месяц.

        Если ученика нет, вернёт None. Иначе вернёт сумму оплаты за месяц.
        """
        return mark_safe(f'<a href="{redirect("certificate_download", obj.number).url}">Скачать</a>')

    download_cert.short_description = "Сертификат"
