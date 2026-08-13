from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from Course.models import Student
from .ai_review import AIReviewStateError, generate_ai_review_draft
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
class ProjectCategoriesAdmin(ModelAdmin):
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
class ProjectForReviewAdmin(ModelAdmin):
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
        'ai_draft_link',
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

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('code_review')

    def ai_draft_link(self, project):
        reviews = list(project.code_review.all())
        if not reviews:
            return '-'
        review = reviews[0]
        if review.is_ai_generated:
            label = review.get_ai_generation_status_display()
        else:
            label = 'Ручное ревью'
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:codereview_codereview_change', args=(review.pk,)),
            label,
        )

    ai_draft_link.short_description = 'Черновик ревью'


@admin.register(CodeReview)
class CodeReviewAdmin(ModelAdmin):
    """
    Ревью проектов.
    """
    fields = (
        'project',
        'is_ai_generated',
        'ai_generation_status',
        'ai_model',
        'ai_source_summary',
        'ai_generation_error',
        'ai_generated_at',
        'problems',
        'amount_problems',
        'code_quality',
        'code_architecture',
        'code_standards',
        'code_principles',
        'code_style',
        'code_wishes',
        'status',
        'is_published',
        'approved_by',
        'approved_at',
        'created_at',
    )
    list_display = (
        'project',
        'is_published',
        'status',
        'created_at',
    )
    list_display_links = (
        'project',
    )
    readonly_fields = (
        'is_ai_generated',
        'ai_generation_status',
        'ai_model',
        'ai_source_summary',
        'ai_generation_error',
        'ai_generated_at',
        'approved_by',
        'approved_at',
        'created_at',
    )
    empty_value_display = '-пустой-'
    list_filter = ('ai_generation_status', 'is_published', 'status')
    list_per_page = 64
    list_max_show_all = 8
    actions = ('regenerate_ai_drafts',)

    def generation_state(self, review):
        return review.get_ai_generation_status_display()

    generation_state.short_description = 'Черновик ИИ'
    generation_state.admin_order_field = 'ai_generation_status'

    def save_model(self, request, obj, form, change):
        previously_published = False
        if change:
            previously_published = CodeReview.objects.get(pk=obj.pk).is_published
        if obj.is_published and not previously_published:
            obj.approved_by = request.user
            obj.approved_at = timezone.now()
        elif not obj.is_published and previously_published:
            obj.approved_by = None
            obj.approved_at = None
        super().save_model(request, obj, form, change)

    @admin.action(description='Повторно сформировать черновики ИИ (не более 5)')
    def regenerate_ai_drafts(self, request, queryset):
        reviews = list(queryset.select_related('project__category')[:6])
        if queryset.count() > 5:
            self.message_user(
                request,
                'Выберите не более 5 ревью: это ограничение защищает расходы на API.',
                level='error',
            )
            return

        ready_count = 0
        failed_count = 0
        for review in reviews:
            try:
                draft = generate_ai_review_draft(review.project)
            except AIReviewStateError as error:
                failed_count += 1
                self.message_user(request, f'{review}: {error}', level='warning')
                continue
            if draft.ai_generation_status == 'ready':
                ready_count += 1
            else:
                failed_count += 1

        if ready_count:
            self.message_user(request, f'Черновиков подготовлено: {ready_count}.')
        if failed_count:
            self.message_user(
                request,
                f'Не удалось подготовить черновиков: {failed_count}. Подробности есть в карточках.',
                level='warning',
            )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "project":
            projects = ProjectForReview.objects.filter(
                status=False,
            ).order_by('-created_at')
            kwargs["queryset"] = projects
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
