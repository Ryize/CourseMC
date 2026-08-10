from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Q

from Course.models import Student
from .models import ProjectCategories, ProjectForReview, CodeReview


class ProjectStudentScopeListFilter(SimpleListFilter):
    """По умолчанию показывает текущих учеников, архив — по явному выбору."""

    title = 'Ученики'
    parameter_name = 'student_scope'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Текущие'),
            ('archive', 'Архив'),
        )

    def choices(self, changelist):
        yield {
            'selected': self.value() in (None, 'active'),
            'query_string': changelist.get_query_string(
                {self.parameter_name: 'active'},
                [],
            ),
            'display': 'Текущие',
        }
        yield {
            'selected': self.value() == 'archive',
            'query_string': changelist.get_query_string(
                {self.parameter_name: 'archive'},
                [],
            ),
            'display': 'Архив',
        }

    def queryset(self, request, queryset):
        active_students = Q(
            user__is_learned=True,
            user__groups__is_studies=True,
        )
        if self.value() == 'archive':
            return queryset.exclude(active_students)
        return queryset.filter(active_students)


class ProjectStudentListFilter(SimpleListFilter):
    """Список учеников соответствует выбранному режиму текущих/архивных."""

    title = 'Ученик'
    parameter_name = 'student'

    def lookups(self, request, model_admin):
        active_scope = request.GET.get('student_scope') != 'archive'
        students = Student.objects.order_by('user__username', 'pk')
        if active_scope:
            students = students.filter(is_learned=True, groups__is_studies=True)
        else:
            students = students.exclude(
                is_learned=True,
                groups__is_studies=True,
            )
        return tuple(students.values_list('pk', 'user__username'))

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        return queryset.filter(user_id=self.value())


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
    list_filter = (
        ProjectStudentScopeListFilter,
        ProjectStudentListFilter,
        'status',
        'category',
    )
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
        'problems',
        'amount_problems',
        'code_quality',
        'code_architecture',
        'code_standards',
        'code_principles',
        'code_style',
        'code_wishes',
        'status',
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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "project":
            projects = ProjectForReview.objects.filter(
                status=False,
            ).order_by('-created_at')
            kwargs["queryset"] = projects
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
