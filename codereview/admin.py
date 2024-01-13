from django.contrib import admin
from .models import ProjectCategories, ProjectForReview, CodeReview


@admin.register(ProjectCategories)
class ProjectCategoriesAdmin(admin.ModelAdmin):
    """
    Категории проектов.
    """
    fields = (
        'title',
        'min_lines',
        'min_cognetive',
        'max_cognetive',
    )
    list_display = (
        'title',
        'min_lines',
        'min_cognetive',
        'max_cognetive',
    )
    list_display_links = (
        'title',
        'min_lines',
        'min_cognetive',
        'max_cognetive',
    )
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8


@admin.register(ProjectForReview)
class ProjectForReviewAdmin(admin.ModelAdmin):
    """
    Проекты на ревью.
    """
    fields = (
        'user',
        'category',
        'github',
        'comment',
        'cognetive',
        'lines',
        'status',
        'created_at',
    )
    list_display = (
        'user',
        'category',
        'status',
        'created_at',
    )
    list_display_links = (
        'user',
        'category',
        'status',
        'created_at',
    )
    readonly_fields = ('cognetive', 'lines', 'created_at')
    list_filter = ('status', 'category', 'user')
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8


@admin.register(CodeReview)
class CodeReviewAdmin(admin.ModelAdmin):
    """
    Ревью проектов.
    """
    fields = (
        'project',
        'status',
        'review',
        'created_at',
    )
    list_display = (
        'project',
        'status',
        'created_at',
    )
    list_display_links = (
        'project',
        'status',
        'created_at',
    )
    readonly_fields = ('created_at',)
    empty_value_display = '-пустой-'
    list_filter = ('status',)
    list_per_page = 64
    list_max_show_all = 8
