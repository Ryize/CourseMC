from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from interview.models import (
    InterviewQuestion,
    InterviewQuestionCategory,
    LiveCodingTask,
    MockInterview,
    MockInterviewAnswer,
    MockInterviewFile,
    MockInterviewSettings,
)


@admin.register(InterviewQuestion)
class InterviewQuestionAdmin(ModelAdmin):
    fields = (
        'title',
        'theme',
        'percent',
        'complexity',
        'use_in_mock',
        'mock_section',
        'mock_level',
    )
    list_display = (
        'title',
        'theme',
        'percent',
        'complexity',
        'use_in_mock',
        'mock_section',
        'mock_level',
    )
    list_display_links = (
        'title',
    )
    list_editable = ('use_in_mock', 'mock_section', 'mock_level')
    list_filter = (
        'use_in_mock',
        'mock_section',
        'mock_level',
        'theme',
        'complexity',
    )
    search_fields = ('title',)
    actions = ('add_to_mock', 'remove_from_mock')
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8

    @admin.action(description='Добавить выбранные вопросы в мок-собеседование')
    def add_to_mock(self, request, queryset):
        updated = queryset.exclude(mock_section='').update(use_in_mock=True)
        self.message_user(
            request,
            f'Добавлено вопросов: {updated}. У вопросов без блока сначала выберите блок.',
        )

    @admin.action(description='Убрать выбранные вопросы из мок-собеседования')
    def remove_from_mock(self, request, queryset):
        updated = queryset.update(use_in_mock=False)
        self.message_user(request, f'Убрано вопросов: {updated}.')


@admin.register(InterviewQuestionCategory)
class InterviewQuestionCategoryAdmin(ModelAdmin):
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


@admin.register(LiveCodingTask)
class LiveCodingTaskAdmin(ModelAdmin):
    fields = (
        'title', 'description', 'category', 'level', 'starter_file',
        'frameworks', 'complexity', 'duration_minutes', 'is_active',
    )
    list_display = (
        'title', 'category', 'level', 'framework_names', 'complexity',
        'duration_minutes', 'is_active',
    )
    list_filter = ('is_active', 'category', 'level', 'complexity', 'frameworks')
    search_fields = ('title', 'description')
    filter_horizontal = ('frameworks',)

    @admin.display(description='Фреймворки')
    def framework_names(self, obj):
        names = list(obj.frameworks.values_list('title', flat=True))
        return ', '.join(names) if names else 'Универсальное'


@admin.register(MockInterviewSettings)
class MockInterviewSettingsAdmin(ModelAdmin):
    fields = ('weekly_attempt_limit', 'updated_at')
    readonly_fields = ('updated_at',)
    list_display = ('__str__', 'weekly_attempt_limit', 'updated_at')

    def has_add_permission(self, request):
        return not MockInterviewSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class MockInterviewAnswerInline(TabularInline):
    model = MockInterviewAnswer
    fields = (
        'position', 'section', 'question_snapshot', 'answer_text', 'result',
        'ai_comment',
    )
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MockInterview)
class MockInterviewAdmin(ModelAdmin):
    fields = (
        'user', 'level', 'framework_list', 'status_badge', 'score_summary', 'summary',
        'strengths', 'weaknesses', 'task_title', 'task_description',
        'live_coding_answer', 'live_coding_repository_url',
        'live_coding_comment', 'solution_file_links',
        'ai_model', 'ai_error', 'started_at', 'theory_completed_at',
        'analysis_started_at', 'completed_at',
    )
    readonly_fields = fields
    list_display = (
        'user', 'level', 'framework_list', 'status_badge', 'overall_score_display',
        'started_at', 'completed_at',
    )
    list_filter = ('level', 'status', 'frameworks', 'started_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    list_select_related = ('user',)
    date_hierarchy = 'started_at'
    inlines = (MockInterviewAnswerInline,)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).prefetch_related(
            'frameworks', 'solution_files',
        )
        if request.user.is_superuser:
            return queryset
        return queryset.filter(
            user__course_profile__groups__teacher__user=request.user,
        ).distinct()

    def has_view_permission(self, request, obj=None):
        has_permission = (
            super().has_view_permission(request, obj)
            or request.user.has_perm('interview.view_interviewquestion')
        )
        if not has_permission:
            return False
        if obj is None or request.user.is_superuser:
            return True
        try:
            return obj.user.course_profile.groups.teacher.user_id == request.user.pk
        except AttributeError:
            return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description='Фреймворки')
    def framework_list(self, obj):
        return ', '.join(item.title for item in obj.frameworks.all()) or '—'

    @display(
        description='Статус',
        ordering='status',
        label={
            MockInterview.Status.THEORY: 'info',
            MockInterview.Status.LIVE_CODING: 'warning',
            MockInterview.Status.ANALYZING: 'warning',
            MockInterview.Status.COMPLETED: 'success',
            MockInterview.Status.FAILED: 'danger',
            MockInterview.Status.ABANDONED: 'info',
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @admin.display(description='Итог', ordering='overall_score')
    def overall_score_display(self, obj):
        return f'{obj.overall_score}%' if obj.overall_score is not None else '—'

    @admin.display(description='Оценки')
    def score_summary(self, obj):
        if obj.overall_score is None:
            return 'Оценка ещё не готова'
        return format_html(
            '<b>Итог: {}%</b> · теория: {}% · лайвкодинг: {}%',
            obj.overall_score, obj.theory_score, obj.live_coding_score,
        )

    @admin.display(description='Файлы решения')
    def solution_file_links(self, obj):
        files = list(obj.solution_files.all())
        if not files:
            return '—'
        return format_html_join(
            '<br>', '<a href="{}">{}</a>',
            ((reverse('mock_solution_file_download', args=(item.pk,)), item.original_name) for item in files),
        )


@admin.register(MockInterviewAnswer)
class MockInterviewAnswerAdmin(ModelAdmin):
    def has_module_permission(self, request):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(
            interview__user__course_profile__groups__teacher__user=request.user,
        ).distinct()


@admin.register(MockInterviewFile)
class MockInterviewFileAdmin(ModelAdmin):
    def has_module_permission(self, request):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(
            interview__user__course_profile__groups__teacher__user=request.user,
        ).distinct()
