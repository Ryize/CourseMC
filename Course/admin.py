from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter

from .models import *


@admin.register(Student)
class PersonAdmin(admin.ModelAdmin):
    fields = (
        'name',
        'contact',
        'email',
        'password',
        'groups',
        'is_learned',
        'last_session',
        'created_at',
    )
    list_display = (
        'id',
        'name',
        'contact',
        'groups',
        'is_learned',
        'last_session',
    )
    list_display_links = (
        'id',
        'name',
        'groups',
        'contact',
        'last_session',
    )
    list_filter = (
        'groups',
        'is_learned',
    )
    readonly_fields = ('created_at', 'last_session',)
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
        'title',
        'is_studies',
    )
    readonly_fields = ('created_at',)
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ['title']


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    content = forms.CharField(widget=CKEditorUploadingWidget())
    fields = (
        'theme',
        'group',
        'weekday',
        'time_lesson',
        'lesson_materials',
        'absent',
        'lesson_type',
        'is_display',
    )
    list_display = ('id', 'theme', 'group', 'weekday', 'time_lesson', 'is_display')
    list_display_links = (
        'theme',
        'group',
        'weekday',
        'time_lesson',
    )
    list_filter = ('group', 'weekday', 'time_lesson', 'lesson_type', 'is_display')
    list_editable = ('is_display',)
    empty_value_display = '-пустой-'
    list_per_page = 66
    list_max_show_all = 8
    search_fields = (
        'theme',
        'lesson_materials',
    )
    date_hierarchy = 'weekday'


@admin.register(StudentQuestion)
class StudentQuestionAdmin(admin.ModelAdmin):
    fields = (
        'group',
        'question',
        'solved',
    )
    list_display = (
        'group',
        'question',
        'solved',
        'created_at',
    )
    list_display_links = (
        'group',
        'question',
        'solved',
    )
    list_filter = (
        'group',
        'created_at',
        'solved',
    )
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ['created_at']


class CountryFilter(SimpleListFilter):
    title = 'Учителя'
    parameter_name = 'teacher'

    def lookups(self, request, model_admin):
        teachers = set([obj.teacher for obj in model_admin.model.objects.all()])
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
        'group',
        'weekday',
        'duration',
        'time_lesson',
    )
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ['group']

    def get_queryset(self, request):
        if request.user.is_superuser:
            return ClassesTimetable.objects.all()
        return ClassesTimetable.objects.filter(teacher__username=request.user.username).all()

    def _order_func(self, i):
        date = {
            'Понедельник': 1,
            'Вторник': 2,
            'Среда': 3,
            'Четверг': 4,
            'Пятница': 5,
            'Суббота': 6,
            'Воскресенье': 7,
        }
        return date[i.weekday]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return (CountryFilter,) + self.list_filter
        return self.list_filter

    def get_list_display(self, request):
        if request.user.is_superuser:
            return ('teacher',) + self.list_filter
        return self.list_display

    def get_list_display_links(self, request, list_display):
        if request.user.is_superuser:
            return ('teacher',) + list_display
        return list_display
