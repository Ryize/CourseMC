from datetime import timedelta
from dataclasses import dataclass
import random

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    InterviewQuestion,
    InterviewQuestionCategory,
    LiveCodingTask,
    MockInterview,
    MockInterviewAllowance,
    MockInterviewAnswer,
    MockInterviewSettings,
)


SECTION_COUNTS = {
    MockInterviewAnswer.Section.GENERAL: 4,
    MockInterviewAnswer.Section.PYTHON: 5,
    MockInterviewAnswer.Section.OOP: 3,
}
FRAMEWORK_QUESTION_COUNT = 3
ANSWER_COOLDOWNS = {
    MockInterviewAnswer.Result.GOOD: timedelta(days=14),
    MockInterviewAnswer.Result.PARTIAL: timedelta(days=7),
    MockInterviewAnswer.Result.WRONG: timedelta(days=2),
}
LIVE_CODING_LEVELS = {
    MockInterview.Level.JUNIOR: LiveCodingTask.Level.JUNIOR,
    MockInterview.Level.MIDDLE: LiveCodingTask.Level.MIDDLE,
    # Для Senior пока используем более сложный пул Middle. Отдельного Senior-пула
    # нет намеренно: текущий каталог разделён на Junior и Middle.
    MockInterview.Level.SENIOR: LiveCodingTask.Level.MIDDLE,
}
RANDOM_LIVE_CODING_CATEGORY = 'random'
MOCK_INTERVIEW_LIMIT_WINDOW = timedelta(days=7)


@dataclass(frozen=True)
class MockInterviewAvailability:
    limit: int
    used: int
    remaining: int
    next_available_at: object | None

    @property
    def can_start(self):
        return self.remaining > 0


def mock_interview_availability(user, now=None, lock_settings=False):
    """Доступность новой попытки в скользящем окне за последние 7 дней."""
    now = now or timezone.now()
    settings_object = MockInterviewSettings.load()
    if lock_settings:
        settings_object = (
            MockInterviewSettings.objects
            .select_for_update()
            .get(pk=settings_object.pk)
        )
    limit = settings_object.weekly_attempt_limit
    if limit > 0:
        allowances = MockInterviewAllowance.objects.filter(user=user)
        if lock_settings:
            allowances = allowances.select_for_update()
        extra_attempts = allowances.values_list('extra_attempts', flat=True).first()
        limit += extra_attempts or 0
    attempts = (
        MockInterview.objects
        .filter(user=user, started_at__gte=now - MOCK_INTERVIEW_LIMIT_WINDOW)
        .order_by('started_at', 'pk')
    )
    started_at_values = list(attempts.values_list('started_at', flat=True))
    used = len(started_at_values)
    remaining = max(0, limit - used)
    next_available_at = None
    if limit > 0 and used >= limit:
        blocking_attempt_index = used - limit
        next_available_at = (
            started_at_values[blocking_attempt_index]
            + MOCK_INTERVIEW_LIMIT_WINDOW
        )
    return MockInterviewAvailability(
        limit=limit,
        used=used,
        remaining=remaining,
        next_available_at=next_available_at,
    )


def _limit_error(availability):
    if availability.next_available_at is None:
        return 'Новые мок-собеседования временно отключены.'
    available_at = timezone.localtime(
        availability.next_available_at,
    ).strftime('%d.%m.%Y в %H:%M')
    return (
        f'Доступно не более {availability.limit} мок-собеседований за 7 дней. '
        f'Следующую попытку можно начать {available_at}.'
    )


def questions_on_cooldown(user, now=None):
    """IDs вопросов, которые ученику пока рано показывать повторно."""
    now = now or timezone.now()
    rows = (
        MockInterviewAnswer.objects
        .filter(
            interview__user=user,
            interview__status=MockInterview.Status.COMPLETED,
            original_question__isnull=False,
            result__in=ANSWER_COOLDOWNS,
        )
        .exclude(interview__completed_at__isnull=True)
        .order_by(
            'original_question_id',
            '-interview__completed_at',
            '-pk',
        )
        .values_list(
            'original_question_id',
            'result',
            'interview__completed_at',
        )
    )
    seen_question_ids = set()
    blocked_question_ids = set()
    for question_id, result, completed_at in rows.iterator():
        if question_id in seen_question_ids:
            continue
        seen_question_ids.add(question_id)
        if completed_at >= now - ANSWER_COOLDOWNS[result]:
            blocked_question_ids.add(question_id)
    return blocked_question_ids


def _weighted_sample(queryset, amount):
    pool = list(queryset)
    if len(pool) < amount:
        raise ValidationError(
            'На выбранном уровне пока недостаточно новых вопросов. '
            'Вернитесь через пару дней или выберите другой уровень.',
        )
    selected = []
    while pool and len(selected) < amount:
        weights = [max(1, question.percent) for question in pool]
        question = random.choices(pool, weights=weights, k=1)[0]
        selected.append(question)
        pool.remove(question)
    return selected


def _live_coding_task(user, level, category):
    used_task_ids = (
        MockInterview.objects
        .filter(user=user, live_coding_task__isnull=False)
        .values_list('live_coding_task_id', flat=True)
    )

    tasks = LiveCodingTask.objects.filter(
        is_active=True,
        level=LIVE_CODING_LEVELS[level],
    ).exclude(pk__in=used_task_ids)
    if category != RANDOM_LIVE_CODING_CATEGORY:
        tasks = tasks.filter(category=category)
    tasks = list(tasks)
    if not tasks:
        return None

    if category == RANDOM_LIVE_CODING_CATEGORY:
        # Категории равновероятны независимо от количества заданий в каждой.
        available_categories = sorted({task.category for task in tasks})
        category = random.choice(available_categories)
        tasks = [task for task in tasks if task.category == category]
    return random.choice(tasks)


@transaction.atomic
def create_mock_interview(
    user,
    frameworks,
    level=MockInterview.Level.JUNIOR,
    live_coding_category=RANDOM_LIVE_CODING_CATEGORY,
):
    frameworks = list(frameworks)
    if not frameworks:
        raise ValidationError('Выберите хотя бы один фреймворк.')
    if level not in MockInterview.Level.values:
        raise ValidationError('Выберите корректный уровень собеседования.')
    if live_coding_category not in {
        RANDOM_LIVE_CODING_CATEGORY,
        *LiveCodingTask.Category.values,
    }:
        raise ValidationError('Выберите корректную категорию задачи.')

    availability = mock_interview_availability(
        user,
        lock_settings=True,
    )
    if not availability.can_start:
        raise ValidationError(_limit_error(availability))

    selected = []
    excluded_question_ids = questions_on_cooldown(user)
    for section, amount in SECTION_COUNTS.items():
        questions = InterviewQuestion.objects.filter(
            use_in_mock=True,
            mock_section=section,
            mock_level=level,
        ).exclude(pk__in=excluded_question_ids).select_related('theme')
        selected.extend((section, question) for question in _weighted_sample(
            questions,
            amount,
        ))

    for framework in frameworks:
        questions = InterviewQuestion.objects.filter(
            use_in_mock=True,
            mock_section=InterviewQuestion.MockSection.FRAMEWORK,
            mock_level=level,
            theme=framework,
        ).exclude(pk__in=excluded_question_ids).select_related('theme')
        selected.extend(
            (MockInterviewAnswer.Section.FRAMEWORK, question)
            for question in _weighted_sample(questions, FRAMEWORK_QUESTION_COUNT)
        )

    task = _live_coding_task(user, level, live_coding_category)
    if task is None:
        raise ValidationError(
            'Для выбранных уровня и категории пока нет нового задания '
            'лайвкодинга. Вы уже проходили все доступные задания.',
        )

    interview = MockInterview.objects.create(
        user=user,
        level=level,
        live_coding_task=task,
        task_title=task.title,
        task_description=task.description,
    )
    interview.frameworks.add(*frameworks)
    MockInterviewAnswer.objects.bulk_create([
        MockInterviewAnswer(
            interview=interview,
            original_question=question,
            section=section,
            category_snapshot=question.theme.title if question.theme else '',
            question_snapshot=question.title,
            position=position,
        )
        for position, (section, question) in enumerate(selected, start=1)
    ])
    return interview
