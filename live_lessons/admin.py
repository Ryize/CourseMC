from django.contrib import admin
from django import forms

from .models import (LiveLesson, LiveLessonAttachment, LiveLessonChatArchive,
                     LiveLessonMessage, LiveLessonRemoval, LiveLessonReschedule)


class LiveLessonAdminForm(forms.ModelForm):
    class Meta:
        model = LiveLesson
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        audience = cleaned.get('audience')
        additional = cleaned.get('additional_groups')
        teacher = cleaned.get('teacher')
        if audience == LiveLesson.Audience.OPEN and additional and additional.exists():
            self.add_error('additional_groups', 'Открытый урок не привязан к группам.')
        if audience == LiveLesson.Audience.GROUPS and additional and teacher:
            if additional.exclude(teacher=teacher, is_studies=True).exists():
                self.add_error('additional_groups', 'Выберите действующие группы этого преподавателя.')
            if cleaned.get('group') and additional.filter(pk=cleaned['group'].pk).exists():
                self.add_error('additional_groups', 'Основная группа уже выбрана.')
        return cleaned


class LiveLessonRescheduleInline(admin.TabularInline):
    model = LiveLessonReschedule
    extra = 0
    can_delete = False
    readonly_fields = ('old_scheduled_at', 'new_scheduled_at', 'reason', 'changed_by', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LiveLesson)
class LiveLessonAdmin(admin.ModelAdmin):
    form = LiveLessonAdminForm
    list_display = ('title', 'audience', 'group', 'teacher', 'scheduled_at', 'status', 'origin')
    list_filter = ('status', 'audience', 'origin', 'group')
    search_fields = ('title', 'group__title', 'additional_groups__title', 'teacher__user__username')
    readonly_fields = ('public_id', 'started_at', 'ended_at', 'created_at', 'updated_at')
    filter_horizontal = ('additional_groups',)
    inlines = (LiveLessonRescheduleInline,)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj:
            return (*fields, 'group', 'additional_groups', 'audience',
                    'teacher', 'scheduled_at', 'status', 'origin')
        return fields

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LiveLessonReschedule)
class LiveLessonRescheduleAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'old_scheduled_at', 'new_scheduled_at', 'changed_by', 'created_at')
    search_fields = ('lesson__title', 'lesson__group__title')
    readonly_fields = ('lesson', 'old_scheduled_at', 'new_scheduled_at', 'reason', 'changed_by', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LiveLessonMessage)
class LiveLessonMessageAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'author', 'guest_name', 'created_at', 'body')
    search_fields = ('lesson__title', 'author__username', 'guest_name', 'body')
    readonly_fields = ('lesson', 'author', 'guest_id', 'guest_name', 'body', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LiveLessonAttachment)
class LiveLessonAttachmentAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'message', 'size', 'content_type')
    readonly_fields = ('message', 'file', 'original_name', 'size', 'content_type')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LiveLessonRemoval)
class LiveLessonRemovalAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'identity', 'removed_by', 'created_at')
    search_fields = ('lesson__title', 'identity')
    readonly_fields = ('lesson', 'identity', 'removed_by', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(LiveLessonChatArchive)
class LiveLessonChatArchiveAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'group', 'schedule', 'created_by', 'created_at')
    list_filter = ('group', 'created_at')
    search_fields = ('lesson__title', 'group__title', 'schedule__theme')
    readonly_fields = ('lesson', 'group', 'schedule', 'file', 'last_message_id',
                       'created_by', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
