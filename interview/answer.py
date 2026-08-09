import random

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from interview.models import InterviewQuestionProgress


REPEAT_SHARE = 0.3


def _weighted_sample(questions, amount):
    """Выбирает вопросы без дублей, сохраняя вес их популярности."""
    pool = list(questions)
    selected = []
    while pool and len(selected) < amount:
        weights = [max(1, int(question.percent)) for question in pool]
        question = random.choices(pool, weights=weights, k=1)[0]
        selected.append(question)
        pool.remove(question)
    return selected


def get_questions(data: QuerySet, themes, amount: int, user=None, now=None):
    """Подбирает новые вопросы раньше повторов, не теряя приоритет популярности."""
    candidates = [
        question for question in data
        if question.theme and question.theme.title in themes
    ]
    if user is None:
        return _weighted_sample(candidates, amount)

    now = now or timezone.now()
    progress_by_question_id = {
        progress.question_id: progress
        for progress in InterviewQuestionProgress.objects.filter(
            user=user,
            question_id__in=[question.pk for question in candidates],
        )
    }
    repeat_questions = []
    unseen_questions = []
    due_questions = []

    for question in candidates:
        progress = progress_by_question_id.get(question.pk)
        if progress is None:
            unseen_questions.append(question)
        elif progress.status == InterviewQuestionProgress.Status.REPEAT:
            repeat_questions.append(question)
        elif progress.next_available_at <= now:
            due_questions.append(question)

    repeat_limit = min(
        len(repeat_questions),
        max(1, round(amount * REPEAT_SHARE)),
    )
    selected = _weighted_sample(repeat_questions, repeat_limit)
    remaining = amount - len(selected)
    selected.extend(_weighted_sample(unseen_questions, remaining))
    remaining = amount - len(selected)
    selected.extend(_weighted_sample(due_questions, remaining))
    remaining = amount - len(selected)
    if remaining:
        selected.extend(
            _weighted_sample(
                [question for question in repeat_questions if question not in selected],
                remaining,
            )
        )
    return selected


def mark_questions_as_shown(user, questions, now=None):
    """Неотмеченные вопросы остаются в очереди на повторение."""
    now = now or timezone.now()

    with transaction.atomic():
        for question in questions:
            progress, created = (
                InterviewQuestionProgress.objects
                .select_for_update()
                .get_or_create(
                    user=user,
                    question=question,
                    defaults={
                        'status': InterviewQuestionProgress.Status.REPEAT,
                        'last_shown_at': now,
                        'next_available_at': now,
                    },
                )
            )
            if created:
                continue

            progress.last_shown_at = now
            progress.shown_count += 1
            progress.status = InterviewQuestionProgress.Status.REPEAT
            progress.next_available_at = now
            progress.save(
                update_fields=(
                    'last_shown_at',
                    'shown_count',
                    'status',
                    'next_available_at',
                    'updated_at',
                ),
            )
