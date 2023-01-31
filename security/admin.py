from security.models import BlockedIPAddress, IPVisitors
from django.contrib import admin


@admin.register(BlockedIPAddress)
class BlockedIPAddressAdmin(admin.ModelAdmin):
    fields = ('ip',)
    list_display = ('ip',)
    list_display_links = ('ip',)
    list_per_page = 64
    list_max_show_all = 8


@admin.register(IPVisitors)
class IPVisitorsAdmin(admin.ModelAdmin):
    fields = ('user', 'ip',)
    list_display = ('user', 'ip',)
    list_display_links = ('user', 'ip',)
    list_per_page = 64
    list_max_show_all = 8
