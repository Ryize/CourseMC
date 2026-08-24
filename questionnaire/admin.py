from django.contrib import admin
from django.db.models import Q
from unfold.admin import ModelAdmin

from .models import *


@admin.register(Rating)
class RatingAdmin(ModelAdmin):
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
    search_fields = ["quiz__title", "comment"]


@admin.register(Quiz)
class QuizAdmin(ModelAdmin):
    list_display = ('title', 'topic', 'user', 'lifetime', 'is_archived')
    list_filter = ('topic', 'is_archived', 'lifetime')
    search_fields = ('title', 'description', 'topic', 'user__username')
    list_select_related = ('user',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(
            Q(user=request.user) | Q(teachers_with_access=request.user)
        ).distinct()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request, obj):
            return False
        if obj is None or request.user.is_superuser:
            return True
        return (
            obj.user_id == request.user.pk
            or obj.teachers_with_access.filter(pk=request.user.pk).exists()
        )

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        return obj is None or request.user.is_superuser or obj.user_id == request.user.pk

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        return obj is None or request.user.is_superuser or obj.user_id == request.user.pk


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    list_display = ('question', 'quiz', 'created_at')
    list_filter = ('quiz', 'created_at')
    search_fields = ('question', 'quiz__title')
    list_select_related = ('quiz',)

    def has_module_permission(self, request):
        """Questions are managed through a quiz and opened from analytics."""
        return False

    def has_view_permission(self, request, obj=None):
        return (
            super().has_view_permission(request, obj)
            or request.user.has_perm('questionnaire.view_quiz')
        )


@admin.register(PassedPolls)
class PassedPollsAdmin(ModelAdmin):
    list_display = ('quiz', 'passed_user', 'created_at')
    list_filter = ('quiz', 'created_at')
    search_fields = ('quiz__title', 'passed_user__username')
    list_select_related = ('quiz', 'passed_user')
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(
            Q(quiz__user=request.user)
            | Q(quiz__teachers_with_access=request.user)
            | Q(passed_user__course_profile__groups__teacher__user=request.user)
        ).distinct()

    def has_view_permission(self, request, obj=None):
        has_permission = (
            super().has_view_permission(request, obj)
            or request.user.has_perm('questionnaire.view_quiz')
        )
        if not has_permission:
            return False
        if obj is None or request.user.is_superuser:
            return True
        if (
            obj.quiz.user_id == request.user.pk
            or obj.quiz.teachers_with_access.filter(pk=request.user.pk).exists()
        ):
            return True
        profile = getattr(obj.passed_user, 'course_profile', None)
        return bool(profile and profile.groups.teacher.user_id == request.user.pk)


@admin.register(AnswerQuestion)
class AnswerQuestionAdmin(ModelAdmin):
    list_display = ('answer', 'question', 'correct', 'created_at')
    list_filter = ('correct', 'question__quiz')
    search_fields = ('answer', 'question__question', 'question__quiz__title')
    list_select_related = ('question__quiz',)


@admin.register(UserAnswer)
class UserAnswerAdmin(ModelAdmin):
    list_display = ('user', 'quiz', 'question', 'is_correct', 'created_at')
    list_filter = ('is_correct', 'quiz', 'created_at')
    search_fields = ('user__username', 'quiz__title', 'question__question')
    readonly_fields = ('is_correct', 'created_at')
    list_select_related = ('user', 'quiz', 'question', 'answers')

    def has_module_permission(self, request):
        """Raw answers remain available by URL but are not a menu section."""
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(
            Q(quiz__user=request.user)
            | Q(quiz__teachers_with_access=request.user)
            | Q(user__course_profile__groups__teacher__user=request.user)
        ).distinct()

    def has_view_permission(self, request, obj=None):
        has_permission = (
            super().has_view_permission(request, obj)
            or request.user.has_perm('questionnaire.view_quiz')
        )
        if not has_permission:
            return False
        if obj is None or request.user.is_superuser:
            return True
        if (
            obj.quiz.user_id == request.user.pk
            or obj.quiz.teachers_with_access.filter(pk=request.user.pk).exists()
        ):
            return True
        profile = getattr(obj.user, 'course_profile', None)
        return bool(profile and profile.groups.teacher.user_id == request.user.pk)
