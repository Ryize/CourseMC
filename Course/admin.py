from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import Http404, HttpResponseRedirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import (
    AdminPasswordChangeForm,
    UserChangeForm,
    UserCreationForm,
)

from billing.admin import UserListFilter
from CourseMC.widgets import RichTextEditorWidget
from .curriculum import create_curriculum_draft, publish_curriculum_version
from .forms import ScheduleAdminForm
from .models import *


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


class ActiveGroupListFilter(SimpleListFilter):
    """Показывает только группы, в которых сейчас идут занятия."""

    title = 'Группа обучения'
    parameter_name = 'active_group'

    def lookups(self, request, model_admin):
        return tuple(
            LearnGroup.objects
            .filter(is_studies=True)
            .order_by('title', 'pk')
            .values_list('pk', 'title')
        )

    def queryset(self, request, queryset):
        group_id = self.value()
        if not group_id:
            return queryset

        model_fields = {field.name for field in queryset.model._meta.get_fields()}
        if 'group' in model_fields:
            return queryset.filter(group_id=group_id)
        if 'groups' in model_fields:
            return queryset.filter(groups_id=group_id)
        return queryset.filter(student__groups_id=group_id)


class ActiveStudentListFilter(SimpleListFilter):
    """Оставляет в очереди проверки только действующих учеников."""

    title = 'Ученик'
    parameter_name = 'active_student'

    def lookups(self, request, model_admin):
        return tuple(
            Student.objects
            .filter(is_learned=True, groups__is_studies=True)
            .order_by('user__username', 'pk')
            .values_list('pk', 'user__username')
        )

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        return queryset.filter(student_id=self.value())


class AttentionNeededListFilter(SimpleListFilter):
    title = 'Быстрый фильтр'
    parameter_name = 'requires_attention'

    def lookups(self, request, model_admin):
        return (('yes', 'Требует внимания'),)

    def queryset(self, request, queryset):
        if self.value() != 'yes':
            return queryset
        return queryset.filter(
            status__in=(
                LessonSolution.Status.PENDING,
                LessonSolution.Status.NEEDS_REVISION,
            ),
        )


class WithoutCommentListFilter(SimpleListFilter):
    title = 'Комментарий преподавателя'
    parameter_name = 'without_comment'

    def lookups(self, request, model_admin):
        return (('yes', 'Без комментария'),)

    def queryset(self, request, queryset):
        if self.value() != 'yes':
            return queryset
        return queryset.filter(
            Q(teacher_comment='') | Q(teacher_comment__isnull=True),
        )


class RecentSolutionListFilter(SimpleListFilter):
    title = 'Дата отправки'
    parameter_name = 'recent_submission'

    def lookups(self, request, model_admin):
        return (('week', 'За последние 7 дней'),)

    def queryset(self, request, queryset):
        if self.value() != 'week':
            return queryset
        return queryset.filter(
            submitted_at__gte=timezone.now() - timedelta(days=7),
        )


class MyGroupsListFilter(SimpleListFilter):
    title = 'Группы преподавателя'
    parameter_name = 'my_groups'

    def lookups(self, request, model_admin):
        if LearnGroup.objects.filter(
            teacher__user=request.user,
            is_studies=True,
        ).exists():
            return (('yes', 'Мои группы'),)
        return ()

    def has_output(self):
        return bool(self.lookup_choices)

    def queryset(self, request, queryset):
        if self.value() != 'yes':
            return queryset
        return queryset.filter(
            student__groups__teacher__user=request.user,
            student__groups__is_studies=True,
        )


@admin.register(Student)
class StudentAdmin(ModelAdmin):
    fields = (
        'user',
        'contact',
        'direction',
        'groups',
        'is_learned',
        'created_at',
    )
    list_display = (
        'id',
        'account',
        'contact',
        'groups',
        'directions',
        'is_learned',
    )
    list_display_links = (
        'id',
        'account',
        'groups',
        'directions',
        'contact',
    )
    list_filter = (
        'is_learned',
        'direction',
    )
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user',)
    list_select_related = ('user', 'groups')
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
    search_fields = [
        'contact', 'user__username', 'user__email',
        'groups__title',
    ]

    @admin.display(description='Аккаунт', ordering='user__username')
    def account(self, obj):
        return obj.user.username

    def directions(self, obj) -> str:
        """
        Список направлений ученика.
        """
        return ', '.join([i.title for i in obj.direction.all()])

    directions.short_description = 'Направление'


@admin.register(LearnGroup)
class LearnGroupAdmin(ModelAdmin):
    fields = (
        'title',
        'teacher',
        'is_studies',
        'created_at',
    )
    list_display = (
        'title',
        'teacher',
        'is_studies',
        'created_at',
    )
    list_display_links = (
        'title',
        'teacher',
    )
    list_filter = (
        'is_studies',
    )
    empty_value_display = '-пустой-'
    readonly_fields = ('is_studies', 'created_at')
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ['title']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = Student.objects.filter(user__is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(DirectionStudy)
class DirectionStudyAdmin(ModelAdmin):
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
    actions = ('create_program_draft',)

    @admin.action(description='Создать черновик из опубликованной программы')
    def create_program_draft(self, request, queryset):
        created = 0
        errors = []
        for direction in queryset:
            try:
                create_curriculum_draft(direction, request.user)
                created += 1
            except ValidationError as error:
                errors.extend(error.messages)
        if created:
            self.message_user(
                request,
                f'Создано черновиков: {created}. Редактируйте их в разделе '
                '«Уроки черновика программы».',
                messages.SUCCESS,
            )
        for error in errors:
            self.message_user(request, error, messages.WARNING)


@admin.register(CurriculumVersion)
class CurriculumVersionAdmin(ModelAdmin):
    fields = (
        'direction', 'name', 'status', 'notes', 'created_by',
        'created_at', 'updated_at', 'published_at',
    )
    list_display = (
        'name', 'direction', 'status', 'lesson_count', 'edit_lessons',
        'created_by', 'updated_at', 'published_at',
    )
    list_filter = ('status', 'direction', 'created_at', 'published_at')
    search_fields = ('name', 'direction__title', 'notes')
    list_select_related = ('direction', 'created_by')
    actions = ('publish_selected',)
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_lesson_count=Count('lessons'))

    @admin.display(description='Уроков', ordering='_lesson_count')
    def lesson_count(self, version):
        return version._lesson_count

    @admin.display(description='Содержание')
    def edit_lessons(self, version):
        return format_html(
            '<a href="{}?version__id__exact={}">{}</a>',
            reverse('admin:Course_curriculumlesson_changelist'),
            version.pk,
            'Редактировать' if version.status == version.Status.DRAFT else 'Посмотреть',
        )

    def get_readonly_fields(self, request, obj=None):
        readonly = (
            'direction', 'status', 'created_by', 'created_at',
            'updated_at', 'published_at',
        )
        if obj and obj.status != obj.Status.DRAFT:
            return readonly + ('name', 'notes')
        return readonly

    @admin.action(description='Опубликовать выбранные черновики')
    def publish_selected(self, request, queryset):
        published = 0
        for version in queryset:
            try:
                publish_curriculum_version(version, request.user)
                published += 1
            except ValidationError as error:
                for message in error.messages:
                    self.message_user(
                        request,
                        f'{version}: {message}',
                        messages.ERROR,
                    )
        if published:
            self.message_user(
                request,
                f'Опубликовано версий: {published}.',
                messages.SUCCESS,
            )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        return obj is None or obj.status == obj.Status.DRAFT

    def delete_queryset(self, request, queryset):
        super().delete_queryset(
            request,
            queryset.filter(status=CurriculumVersion.Status.DRAFT),
        )


class CurriculumLessonAdminForm(forms.ModelForm):
    class Meta:
        model = CurriculumLesson
        fields = '__all__'
        widgets = {
            'plan': RichTextEditorWidget(),
            'lesson_materials': RichTextEditorWidget(),
        }


@admin.register(CurriculumLesson)
class CurriculumLessonAdmin(ModelAdmin):
    form = CurriculumLessonAdminForm
    fields = (
        'version', 'source_schedule', 'position', 'theme',
        'plan', 'lesson_materials', 'lesson_type',
    )
    list_display = ('position', 'theme', 'version', 'lesson_type')
    list_display_links = ('theme',)
    list_editable = ('position',)
    list_filter = ('version', 'lesson_type')
    search_fields = ('theme', 'plan', 'lesson_materials', 'version__name')
    list_select_related = ('version__direction', 'source_schedule')
    list_per_page = 100
    ordering = ('version', 'position', 'pk')

    @staticmethod
    def _rich_text_preview(value):
        if not value:
            return '-пустой-'
        return format_html(
            '<div class="cm-rich-text-preview">{}</div>',
            mark_safe(value),
        )

    @admin.display(description='План урока')
    def plan_preview(self, obj):
        return self._rich_text_preview(obj.plan)

    @admin.display(description='Материалы к уроку')
    def lesson_materials_preview(self, obj):
        return self._rich_text_preview(obj.lesson_materials)

    def get_fields(self, request, obj=None):
        if obj and not self.has_change_permission(request, obj):
            return (
                'version', 'source_schedule', 'position', 'theme',
                'plan_preview', 'lesson_materials_preview', 'lesson_type',
            )
        return super().get_fields(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'version':
            kwargs['queryset'] = CurriculumVersion.objects.filter(
                status=CurriculumVersion.Status.DRAFT,
            ).select_related('direction')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if obj and not self.has_change_permission(request, obj):
            return (
                'version', 'source_schedule', 'position', 'theme',
                'plan_preview', 'lesson_materials_preview', 'lesson_type',
            )
        return ('source_schedule',)

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and CurriculumVersion.objects.filter(
                status=CurriculumVersion.Status.DRAFT,
            ).exists()
        )

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        return obj is None or obj.version.status == CurriculumVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        return obj is None or obj.version.status == CurriculumVersion.Status.DRAFT

    def delete_queryset(self, request, queryset):
        super().delete_queryset(
            request,
            queryset.filter(version__status=CurriculumVersion.Status.DRAFT),
        )


@admin.register(Schedule)
class ScheduleAdmin(ModelAdmin):
    form = ScheduleAdminForm
    fieldsets = (
        ('Порядок в программе', {
            'fields': ('direction', 'insert_after', 'position', 'is_archived'),
            'description': (
                'Это опубликованная программа. Рабочие изменения создавайте '
                'через «Версии программы», чтобы ученики не увидели их до '
                'публикации. Прямое редактирование доступно только '
                'суперпользователю как аварийный инструмент.'
            ),
        }),
        ('Содержание урока', {
            'fields': ('theme', 'plan', 'lesson_materials', 'lesson_type'),
        }),
    )
    list_display = (
        'lesson_number',
        'theme',
        'direction',
        'archive_status',
    )
    list_display_links = (
        'theme',
    )
    list_filter = (
        'direction',
        'lesson_type',
        'is_archived',
    )
    readonly_fields = ('position',)
    actions = (
        'move_selected_up',
        'move_selected_down',
        'duplicate_selected',
        'archive_selected',
        'restore_selected',
    )
    empty_value_display = '-пустой-'
    list_per_page = 66
    list_max_show_all = 8
    search_fields = (
        'theme',
        'lesson_materials',
    )

    @staticmethod
    def _rich_text_preview(value):
        if not value:
            return '-пустой-'
        return format_html(
            '<div class="cm-rich-text-preview">{}</div>',
            mark_safe(value),
        )

    @admin.display(description='План урока')
    def plan_preview(self, obj):
        return self._rich_text_preview(obj.plan)

    @admin.display(description='Материалы к уроку')
    def lesson_materials_preview(self, obj):
        return self._rich_text_preview(obj.lesson_materials)

    def get_fieldsets(self, request, obj=None):
        if obj and not self.has_change_permission(request, obj):
            return (
                ('Порядок в программе', {
                    'fields': ('direction', 'position', 'is_archived'),
                    'description': (
                        'Это опубликованная программа. Изменения вносите '
                        'через «Версии программы».'
                    ),
                }),
                ('Содержание урока', {
                    'fields': (
                        'theme', 'plan_preview',
                        'lesson_materials_preview', 'lesson_type',
                    ),
                }),
            )
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and not self.has_change_permission(request, obj):
            readonly.extend(('plan_preview', 'lesson_materials_preview'))
        return tuple(readonly)

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return super().has_change_permission(request, obj)
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('direction')
            .order_by('direction__title', 'is_archived', 'position', 'pk')
        )

    @admin.display(description='№', ordering='position')
    def lesson_number(self, obj):
        return obj.position

    @admin.display(boolean=True, description='Статус')
    def archive_status(self, obj):
        return not obj.is_archived

    @staticmethod
    def _active_lessons(direction_id):
        return list(
            Schedule.objects
            .select_for_update()
            .filter(direction_id=direction_id, is_archived=False)
            .order_by('position', 'pk')
        )

    @staticmethod
    def _apply_order(lessons):
        for position, lesson in enumerate(lessons, start=1):
            if lesson.position != position:
                Schedule.objects.filter(pk=lesson.pk).update(position=position)
                lesson.position = position

    @classmethod
    def _normalize_direction(cls, direction_id):
        cls._apply_order(cls._active_lessons(direction_id))

    @classmethod
    def _place_after(cls, lesson, insert_after):
        lessons = cls._active_lessons(lesson.direction_id)
        lessons = [item for item in lessons if item.pk != lesson.pk]

        if insert_after:
            after_index = next(
                index
                for index, item in enumerate(lessons)
                if item.pk == insert_after.pk
            )
            lessons.insert(after_index + 1, lesson)
        else:
            lessons.append(lesson)
        cls._apply_order(lessons)

    def _move_selected(self, queryset, step):
        direction_ids = queryset.values_list('direction_id', flat=True).distinct()
        for direction_id in direction_ids:
            selected_ids = set(
                queryset
                .filter(direction_id=direction_id, is_archived=False)
                .values_list('pk', flat=True)
            )
            lessons = self._active_lessons(direction_id)
            if step < 0:
                indexes = range(1, len(lessons))
            else:
                indexes = range(len(lessons) - 2, -1, -1)

            for index in indexes:
                neighbour_index = index - 1 if step < 0 else index + 1
                if (
                    lessons[index].pk in selected_ids
                    and lessons[neighbour_index].pk not in selected_ids
                ):
                    lessons[index], lessons[neighbour_index] = (
                        lessons[neighbour_index],
                        lessons[index],
                    )
            self._apply_order(lessons)

    @admin.action(description='Переместить выбранные уроки выше')
    def move_selected_up(self, request, queryset):
        with transaction.atomic():
            self._move_selected(queryset, step=-1)
        self.message_user(request, 'Порядок уроков обновлён.', messages.SUCCESS)

    @admin.action(description='Переместить выбранные уроки ниже')
    def move_selected_down(self, request, queryset):
        with transaction.atomic():
            self._move_selected(queryset, step=1)
        self.message_user(request, 'Порядок уроков обновлён.', messages.SUCCESS)

    @admin.action(description='Создать копии выбранных уроков')
    def duplicate_selected(self, request, queryset):
        copied_count = 0
        with transaction.atomic():
            for lesson in queryset.order_by('direction_id', 'position', 'pk'):
                copied_lesson = Schedule.objects.create(
                    theme=f'{lesson.theme} (копия)',
                    plan=lesson.plan,
                    lesson_materials=lesson.lesson_materials,
                    lesson_type=lesson.lesson_type,
                    direction=lesson.direction,
                )
                if not lesson.is_archived:
                    self._place_after(copied_lesson, lesson)
                copied_count += 1
        self.message_user(
            request,
            f'Создано копий уроков: {copied_count}.',
            messages.SUCCESS,
        )

    @admin.action(description='Архивировать выбранные уроки')
    def archive_selected(self, request, queryset):
        with transaction.atomic():
            directions = list(queryset.values_list('direction_id', flat=True).distinct())
            updated_count = queryset.filter(is_archived=False).update(is_archived=True)
            for direction_id in directions:
                self._normalize_direction(direction_id)
        self.message_user(
            request,
            f'В архив перемещено уроков: {updated_count}.',
            messages.SUCCESS,
        )

    @admin.action(description='Восстановить выбранные уроки из архива')
    def restore_selected(self, request, queryset):
        restored_count = 0
        with transaction.atomic():
            for lesson in queryset.filter(is_archived=True):
                lesson.is_archived = False
                lesson.position = 0
                lesson.save()
                restored_count += 1
            for direction_id in queryset.values_list('direction_id', flat=True).distinct():
                self._normalize_direction(direction_id)
        self.message_user(
            request,
            f'Восстановлено уроков: {restored_count}.',
            messages.SUCCESS,
        )

    def save_model(self, request, obj, form, change):
        previous_direction_id = None
        previous_is_archived = None
        if change:
            previous_lesson = Schedule.objects.only(
                'direction_id',
                'is_archived',
            ).get(pk=obj.pk)
            previous_direction_id = previous_lesson.direction_id
            previous_is_archived = previous_lesson.is_archived
            if previous_direction_id != obj.direction_id:
                obj.position = 0

        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if previous_direction_id and previous_direction_id != obj.direction_id:
                self._normalize_direction(previous_direction_id)

            insert_after = form.cleaned_data.get('insert_after')
            if not obj.is_archived:
                if insert_after:
                    self._place_after(obj, insert_after)
                elif (
                    not change
                    or previous_direction_id != obj.direction_id
                    or previous_is_archived
                ):
                    self._place_after(obj, None)
            elif change and not previous_is_archived:
                self._normalize_direction(obj.direction_id)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser or obj is None:
            return False
        return (
            super().has_delete_permission(request, obj)
            and not obj.solutions.exists()
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
class ClassesTimetableAdmin(ModelAdmin):
    fieldsets = (
        (None, {
            'fields': ('group', 'weekday', 'time_lesson', 'duration',)
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
        ActiveGroupListFilter,
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
            group__teacher__user=request.user,
        )


@admin.register(ApplicationsForTraining)
class ApplicationsForTrainingAdmin(ModelAdmin):
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
class AdditionalLessonsAdmin(ModelAdmin):
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


class LessonSolutionSubmissionInline(TabularInline):
    model = LessonSolutionSubmission
    fields = ('attempt_number', 'submitted_at')
    readonly_fields = ('attempt_number', 'submitted_at')
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LessonSolution)
class LessonSolutionAdmin(ModelAdmin):
    fields = (
        'student',
        'schedule',
        'status',
        'teacher_comment',
        'file_links',
        'reviewed_by',
        'reviewed_at',
        'submitted_at',
        'updated_at',
    )
    list_display = (
        'student',
        'schedule',
        'group',
        'status',
        'submitted_at',
    )
    list_display_links = (
        'student',
        'schedule',
        'group',
        'status',
        'submitted_at',
    )
    list_filter = (
        AttentionNeededListFilter,
        WithoutCommentListFilter,
        RecentSolutionListFilter,
        MyGroupsListFilter,
        'status',
        'schedule__direction',
        ActiveStudentListFilter,
        ActiveGroupListFilter,
    )
    search_fields = ('student__name', 'schedule__theme', 'teacher_comment')
    readonly_fields = (
        'file_links',
        'submitted_at',
        'updated_at',
        'reviewed_by',
        'reviewed_at',
    )
    list_select_related = ('student', 'student__groups', 'schedule', 'reviewed_by')
    list_per_page = 50
    inlines = (LessonSolutionSubmissionInline,)

    def get_queryset(self, request):
        queryset = (
            LessonSolution.objects
            .all()
            .annotate(
                review_priority=Case(
                    When(status=LessonSolution.Status.PENDING, then=Value(0)),
                    When(
                        status=LessonSolution.Status.NEEDS_REVISION,
                        then=Value(1),
                    ),
                    default=Value(2),
                    output_field=IntegerField(),
                ),
            )
        )
        if request.user.is_superuser:
            return queryset
        return queryset.filter(
            student__groups__teacher__user=request.user,
        )

    def get_ordering(self, request):
        return ('review_priority', '-submitted_at')

    def group(self, obj):
        return obj.student.groups

    group.short_description = 'Группа'

    @admin.display(description='Файлы решения')
    def file_links(self, obj):
        if not obj or not obj.files.exists():
            return 'Файлы не прикреплены.'

        return format_html_join(
            mark_safe('<br>'),
            '{} — <a href="{}" target="_blank" rel="noopener">Открыть</a> · '
            '<a href="{}">Скачать</a>',
            (
                (
                    solution_file.original_name,
                    f"{reverse('lesson_solution_file_download', args=(solution_file.pk,))}?view=1",
                    reverse('lesson_solution_file_download', args=(solution_file.pk,)),
                )
                for solution_file in obj.files.all()
            ),
        )

    def save_model(self, request, obj, form, change):
        if obj.status == LessonSolution.Status.PENDING:
            obj.reviewed_by = None
            obj.reviewed_at = None
        elif not change or {
            'status', 'teacher_comment',
        }.intersection(form.changed_data):
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        has_permission = (
            super().has_view_permission(request, obj)
            or request.user.has_perm('Course.view_lessonsolution')
        )
        if not has_permission:
            return False
        return (
            obj is None
            or request.user.is_superuser
            or obj.student.groups.teacher.user_id == request.user.pk
        )

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        return (
            obj is None
            or request.user.is_superuser
            or obj.student.groups.teacher.user_id == request.user.pk
        )

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(LessonSolutionSubmission)
class LessonSolutionSubmissionAdmin(ModelAdmin):
    list_display = ('solution', 'attempt_number', 'submitted_at')
    list_filter = ('submitted_at', 'solution__student__groups')
    search_fields = (
        'solution__student__user__username',
        'solution__schedule__theme',
    )
    readonly_fields = ('solution', 'attempt_number', 'submitted_at')
    list_select_related = (
        'solution__student__user',
        'solution__student__groups__teacher__user',
        'solution__schedule',
    )
    date_hierarchy = 'submitted_at'

    def has_module_permission(self, request):
        """Keep drill-down URLs available without cluttering the admin menu."""
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(
            solution__student__groups__teacher__user=request.user,
        )

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request, obj):
            return False
        return (
            obj is None
            or request.user.is_superuser
            or obj.solution.student.groups.teacher.user_id == request.user.pk
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StudentQuestion)
class StudentQuestionAdmin(ModelAdmin):
    list_display = ('question', 'group', 'solved', 'created_at')
    list_filter = ('solved', ActiveGroupListFilter)
    search_fields = ('question', 'group__title')
    readonly_fields = ('created_at',)
    list_select_related = ('group',)


class NotificationReadListFilter(SimpleListFilter):
    title = 'Состояние'
    parameter_name = 'read_state'

    def lookups(self, request, model_admin):
        return (('unread', 'Непрочитанные'), ('read', 'Прочитанные'))

    def queryset(self, request, queryset):
        if self.value() == 'unread':
            return queryset.filter(read_at__isnull=True)
        if self.value() == 'read':
            return queryset.filter(read_at__isnull=False)
        return queryset


@admin.register(TeacherNotification)
class TeacherNotificationAdmin(ModelAdmin):
    list_display = ('open_notification_link', 'kind', 'created_at', 'read_at')
    list_filter = (NotificationReadListFilter, 'kind', 'created_at')
    search_fields = ('title', 'message')
    readonly_fields = (
        'recipient', 'kind', 'title', 'message', 'target_url',
        'event_key', 'created_at', 'read_at',
    )
    actions = ('mark_as_read',)
    date_hierarchy = 'created_at'
    list_select_related = ('recipient',)

    def has_module_permission(self, request):
        """Notifications power badges and links but are not a menu section."""
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(recipient=request.user)

    def get_urls(self):
        return [
            path(
                '<int:notification_id>/open/',
                self.admin_site.admin_view(self.open_notification),
                name='Course_teachernotification_open',
            ),
        ] + super().get_urls()

    @admin.display(description='Уведомление', ordering='title')
    def open_notification_link(self, notification):
        return format_html(
            '<a href="{}">{}</a><span class="block text-subtle text-xs">{}</span>',
            reverse(
                'admin:Course_teachernotification_open',
                args=(notification.pk,),
            ),
            notification.title,
            notification.message,
        )

    def open_notification(self, request, notification_id):
        notification = TeacherNotification.objects.filter(
            pk=notification_id,
        ).first()
        if notification is None or (
            notification.recipient_id != request.user.pk
            and not request.user.is_superuser
        ):
            raise Http404
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=('read_at',))
        return HttpResponseRedirect(notification.target_url)

    @admin.action(description='Отметить выбранные уведомления прочитанными')
    def mark_as_read(self, request, queryset):
        queryset.filter(read_at__isnull=True).update(read_at=timezone.now())

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
