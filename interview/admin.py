from django.contrib import admin

from interview.models import InterviewQuestionCategory, InterviewQuestion


@admin.register(InterviewQuestion)
class InterviewQuestionAdmin(admin.ModelAdmin):
    fields = (
        'title',
        'theme',
        'percent',
    )
    list_display = (
        'title',
        'theme',
        'percent',
    )
    list_display_links = (
        'title',
        'theme',
        'percent',
    )
    list_filter = (
        'theme',
    )
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8


@admin.register(InterviewQuestionCategory)
class InterviewQuestionCategoryAdmin(admin.ModelAdmin):
    fields = (
        'title',
    )
    list_display = (
        'title',
    )
    list_display_links = (
        'title',
    )
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
