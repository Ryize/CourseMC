from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter

from billing.admin import UserListFilter
from .models import *


class GroupListFilter(admin.SimpleListFilter):
    title = 'Группы'

    parameter_name = 'group'

    def lookups(self, request, model_admin) -> tuple:
        posts = set([group.title for group in LearnGroup.objects.all() if
                     group.is_studies])
        result_data = []
        for post in posts:
            result_data.append((post, post,))
        return tuple(result_data)

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        return queryset.filter(group__title=self.value())


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    fields = (
        'name',
        'contact',
        'email',
        'password',
        'groups',
        'is_learned',
        'created_at',
    )
    list_display = (
        'id',
        'name',
        'contact',
        'groups',
        'is_learned',
    )
    list_display_links = (
        'id',
        'name',
        'groups',
        'contact',
    )
    list_filter = (
        GroupListFilter,
        'is_learned',
    )
    readonly_fields = ('created_at',)
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ['name', 'contact', 'email', 'groups']


@admin.register(LearnGroup)
class LearnGroupAdmin(admin.ModelAdmin):
    fields = (
        'title',
        'is_studies',
        'created_at',
    )
    list_display = (
        'id',
        'title',
        'is_studies',
        'created_at',
    )
    list_display_links = (
        'id',
        'title',
    )
    list_filter = (
        'is_studies',
    )
    empty_value_display = '-пустой-'
    readonly_fields = ('created_at',)
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ['title']


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    content = forms.CharField(widget=CKEditorUploadingWidget())
    fields = (
        'for_filter',
        'theme',
        'lesson_materials',
        'lesson_type',
    )
    list_display = (
        'pk',
        'theme',
        'for_filter',
    )
    list_display_links = (
        'theme',
    )
    list_filter = (
        'lesson_type',
    )
    empty_value_display = '-пустой-'
    list_per_page = 66
    list_max_show_all = 8
    search_fields = (
        'theme',
        'lesson_materials',
    )


class CountryFilter(SimpleListFilter):
    title = 'Учителя'
    parameter_name = 'teacher'

    def lookups(self, request, model_admin):
        teachers = set(
            [obj.teacher for obj in model_admin.model.objects.all()])
        return [(teacher.id, teacher.username) for teacher in teachers]

    def queryset(self, request, queryset):
        return queryset.filter(teacher__is_staff=True)


@admin.register(ClassesTimetable)
class ClassesTimetableAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {
            'fields': ('teacher', 'group')
        }),
        (None, {
            'fields': ('weekday', 'time_lesson', 'duration',)
        }),

    )
    list_display = (
        'group',
        'weekday',
        'time_lesson',
        'duration',
    )
    list_display_links = (
        'group',
        'weekday',
        'time_lesson',
        'duration',
    )
    list_filter = (
        'weekday',
        GroupListFilter,
        'duration',
        'time_lesson',
    )
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ['group']

    def get_queryset(self, request):
        if request.user.is_superuser:
            return ClassesTimetable.objects.all()
        return ClassesTimetable.objects.filter(
            teacher__username=request.user.username
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ApplicationsForTraining)
class ApplicationsForTrainingAdmin(admin.ModelAdmin):
    fields = (
        'student',
        'created_at',
        'descry',
    )
    list_display = (
        'student',
        'created_at',
        'descry',
    )
    list_display_links = (
        'student',
        'created_at',
    )
    list_filter = (
        'descry',
    )
    readonly_fields = ('created_at',)
    empty_value_display = 'не указанно'
    list_editable = ('descry',)
    list_per_page = 64
    list_max_show_all = 8


@admin.register(AdditionalLessons)
class AdditionalLessonsAdmin(admin.ModelAdmin):
    fields = (
        'group',
        'amount',
    )
    list_display = (
        'group',
        'amount',
    )
    list_display_links = (
        'group',
        'amount',
    )
    empty_value_display = 'не указанно'
    list_per_page = 64
    list_max_show_all = 8
