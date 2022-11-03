from django.contrib import admin

from .models import *


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    fields = (
        "quiz",
        "answer_number",
        "comment",
    )
    list_display = (
        "quiz",
        "answer_number",
        "comment",
    )
    list_display_links = (
        "quiz",
        "answer_number",
        "comment",
    )
    list_filter = (
        "quiz",
        "answer_number",
    )
    empty_value_display = "-пустой-"
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ["quiz", "answer_number", "comment"]


admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(PassedPolls)
