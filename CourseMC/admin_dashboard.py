"""Проверяемая серверная аналитика главной страницы админки."""

import json
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from Course.models import (
    ApplicationsForTraining,
    LearnGroup,
    LessonSolution,
    LessonSolutionSubmission,
    Student,
    StudentQuestion,
)
from codereview.models import CodeReview, ProjectForReview
from interview.models import InterviewQuestionProgress
from questionnaire.models import PassedPolls, Question, Quiz, UserAnswer


PERIODS = (
    (30, '30 дней'),
    (90, '3 месяца'),
    (365, 'Год'),
)
DEFAULT_PERIOD = 90
CHART_COLORS = {
    'primary': 'rgb(99, 102, 241)',
    'success': 'rgb(16, 185, 129)',
    'warning': 'rgb(245, 158, 11)',
    'danger': 'rgb(244, 63, 94)',
    'muted': 'rgb(148, 163, 184)',
}


def _chart(labels, datasets, *, options=None):
    return {
        'has_data': bool(labels),
        'data': json.dumps(
            {'labels': labels, 'datasets': datasets},
            ensure_ascii=False,
        ),
        'options': json.dumps(options or {}, ensure_ascii=False),
    }


def _shorten(value, limit=44):
    value = str(value)
    return value if len(value) <= limit else f'{value[:limit - 1]}…'


def _admin_url(model, action='changelist', object_id=None):
    name = f'admin:{model._meta.app_label}_{model._meta.model_name}_{action}'
    return reverse(name, args=(object_id,)) if object_id else reverse(name)


def _age_label(moment, now):
    if not moment:
        return ''
    elapsed = now - moment
    if elapsed.days:
        return f'{elapsed.days} дн.'
    hours = max(0, elapsed.seconds // 3600)
    return f'{hours} ч.' if hours else 'меньше часа'


def _scope(request):
    groups = (
        LearnGroup.objects
        .filter(is_studies=True, students__is_learned=True)
        .distinct()
        .order_by('title', 'pk')
    )
    if not request.user.is_superuser:
        groups = groups.filter(teacher__user=request.user)

    visible_groups = list(groups)
    visible_group_ids = [group.pk for group in visible_groups]
    requested_group = request.GET.get('group', '')
    selected_group_id = (
        int(requested_group)
        if requested_group.isdigit()
        and int(requested_group) in visible_group_ids
        else None
    )
    selected_group_ids = (
        [selected_group_id]
        if selected_group_id is not None
        else visible_group_ids
    )
    students = Student.objects.filter(
        is_learned=True,
        groups_id__in=selected_group_ids,
    )
    return visible_groups, selected_group_id, students


def _period(request):
    allowed = {days for days, _ in PERIODS}
    try:
        selected = int(request.GET.get('period', DEFAULT_PERIOD))
    except (TypeError, ValueError):
        selected = DEFAULT_PERIOD
    return selected if selected in allowed else DEFAULT_PERIOD


def _week_buckets(start, end):
    first_week = start.date() - timedelta(days=start.weekday())
    last_week = end.date() - timedelta(days=end.weekday())
    weeks = []
    current = first_week
    while current <= last_week:
        weeks.append(current)
        current += timedelta(days=7)
    return weeks


def _week_label(day):
    return day.strftime('%d.%m')


def _solution_activity(student_ids, start, now):
    weeks = _week_buckets(start, now)
    first_attempts = defaultdict(int)
    repeated_attempts = defaultdict(int)
    for submitted_at, attempt_number in (
        LessonSolutionSubmission.objects
        .filter(solution__student_id__in=student_ids, submitted_at__gte=start)
        .values_list('submitted_at', 'attempt_number')
    ):
        week = submitted_at.date() - timedelta(days=submitted_at.weekday())
        target = first_attempts if attempt_number == 1 else repeated_attempts
        target[week] += 1

    first_values = [first_attempts[week] for week in weeks]
    repeated_values = [repeated_attempts[week] for week in weeks]
    has_activity = any(first_values) or any(repeated_values)
    return _chart(
        [_week_label(week) for week in weeks] if has_activity else [],
        [
            {
                'label': 'Первые отправки',
                'data': first_values,
                'borderColor': CHART_COLORS['primary'],
                'backgroundColor': CHART_COLORS['primary'],
                'tension': 0.3,
                'maxTicksXLimit': 12,
                'displayYAxis': True,
            },
            {
                'label': 'Повторные отправки',
                'data': repeated_values,
                'borderColor': CHART_COLORS['warning'],
                'backgroundColor': CHART_COLORS['warning'],
                'tension': 0.3,
            },
        ],
        options={'scales': {'y': {'beginAtZero': True}}},
    )


def _solution_statuses(student_ids):
    totals = dict(
        LessonSolution.objects
        .filter(student_id__in=student_ids)
        .values_list('status')
        .annotate(total=Count('pk'))
    )
    statuses = (
        (LessonSolution.Status.PENDING, ('На', 'проверке'), 'warning'),
        (LessonSolution.Status.NEEDS_REVISION, ('Нужна', 'доработка'), 'danger'),
        (LessonSolution.Status.ACCEPTED, ('Принято',), 'success'),
    )
    labels = [list(label) for _, label, _ in statuses]
    data = [totals.get(status, 0) for status, _, _ in statuses]
    return _chart(
        labels if any(data) else [],
        [{
            'label': 'Решения',
            'data': data,
            'backgroundColor': [
                CHART_COLORS[color] for _, _, color in statuses
            ],
            'displayYAxis': True,
        }],
        options={'scales': {'y': {'beginAtZero': True}}},
    ), totals


def _completed_answer_rows(student_user_ids, start):
    completion_rows = list(
        PassedPolls.objects
        .filter(
            passed_user_id__in=student_user_ids,
            created_at__gte=start,
        )
        .values('quiz_id', 'passed_user_id', 'created_at')
    )
    completed_pairs = {
        (row['quiz_id'], row['passed_user_id']) for row in completion_rows
    }
    if not completed_pairs:
        return completion_rows, []

    answers = [
        row
        for row in (
            UserAnswer.objects
            .filter(
                quiz_id__in={pair[0] for pair in completed_pairs},
                user_id__in={pair[1] for pair in completed_pairs},
            )
            .values('quiz_id', 'user_id', 'question_id', 'is_correct')
        )
        if (row['quiz_id'], row['user_id']) in completed_pairs
    ]
    return completion_rows, answers


def _quiz_results(completions, answers):
    completion_totals = defaultdict(int)
    for completion in completions:
        completion_totals[completion['quiz_id']] += 1

    answer_totals = defaultdict(int)
    correct_totals = defaultdict(int)
    for answer in answers:
        answer_totals[answer['quiz_id']] += 1
        correct_totals[answer['quiz_id']] += int(answer['is_correct'])

    quiz_ids = sorted(
        answer_totals,
        key=lambda quiz_id: (
            completion_totals[quiz_id],
            answer_totals[quiz_id],
        ),
        reverse=True,
    )[:10]
    titles = dict(
        Quiz.objects.filter(pk__in=quiz_ids).values_list('pk', 'title')
    )
    labels = [
        f'{_shorten(titles.get(quiz_id, "Опрос"), 20)} · '
        f'{completion_totals[quiz_id]}'
        for quiz_id in quiz_ids
    ]
    percentages = [
        round(correct_totals[quiz_id] / answer_totals[quiz_id] * 100)
        for quiz_id in quiz_ids
    ]
    return _chart(
        labels,
        [{
            'label': 'Правильных ответов',
            'data': percentages,
            'backgroundColor': CHART_COLORS['primary'],
        }],
        options={
            'indexAxis': 'y',
            'scales': {
                'x': {'beginAtZero': True, 'max': 100},
                'y': {'ticks': {'autoSkip': False}},
            },
        },
    ), percentages


def _difficult_questions(answers):
    totals = defaultdict(int)
    wrong = defaultdict(int)
    for answer in answers:
        question_id = answer['question_id']
        totals[question_id] += 1
        wrong[question_id] += int(not answer['is_correct'])

    eligible_ids = [question_id for question_id, total in totals.items() if total >= 3]
    question_data = {
        row['pk']: row
        for row in (
            Question.objects
            .filter(pk__in=eligible_ids)
            .values('pk', 'question', 'quiz__title')
        )
    }
    ranked = sorted(
        eligible_ids,
        key=lambda question_id: (
            wrong[question_id] / totals[question_id],
            totals[question_id],
        ),
        reverse=True,
    )[:8]
    labels = [
        f'{_shorten(question_data[question_id]["question"], 38)} · '
        f'{totals[question_id]} отв.'
        for question_id in ranked
    ]
    percentages = [
        round(wrong[question_id] / totals[question_id] * 100)
        for question_id in ranked
    ]
    return _chart(
        labels,
        [{
            'label': 'Ошибочных ответов',
            'data': percentages,
            'backgroundColor': CHART_COLORS['danger'],
            'displayYAxis': True,
            'suffixYAxis': '%',
        }],
        options={
            'indexAxis': 'y',
            'scales': {'x': {'beginAtZero': True, 'max': 100}},
        },
    )


def _quiz_activity(completions, start, now):
    weeks = _week_buckets(start, now)
    completion_counts = defaultdict(int)
    users_by_week = defaultdict(set)
    for completion in completions:
        moment = completion['created_at']
        week = moment.date() - timedelta(days=moment.weekday())
        completion_counts[week] += 1
        users_by_week[week].add(completion['passed_user_id'])
    completion_values = [completion_counts[week] for week in weeks]
    unique_student_values = [len(users_by_week[week]) for week in weeks]
    has_activity = any(completion_values)
    return _chart(
        [_week_label(week) for week in weeks] if has_activity else [],
        [
            {
                'label': 'Прохождений',
                'data': completion_values,
                'backgroundColor': CHART_COLORS['primary'],
                'maxTicksXLimit': 12,
                'displayYAxis': True,
            },
            {
                'label': 'Уникальных учеников',
                'data': unique_student_values,
                'borderColor': CHART_COLORS['success'],
                'backgroundColor': CHART_COLORS['success'],
                'type': 'line',
                'tension': 0.3,
            },
        ],
        options={'scales': {'y': {'beginAtZero': True}}},
    )


def _interview_progress(student_user_ids):
    rows = (
        InterviewQuestionProgress.objects
        .filter(user_id__in=student_user_ids)
        .values('question__theme__title', 'status')
        .annotate(total=Count('pk'))
    )
    grouped = defaultdict(lambda: {'answered': 0, 'repeat': 0})
    for row in rows:
        theme = row['question__theme__title'] or 'Без категории'
        key = (
            'answered'
            if row['status'] == InterviewQuestionProgress.Status.ANSWERED
            else 'repeat'
        )
        grouped[theme][key] += row['total']

    themes = sorted(
        grouped,
        key=lambda theme: (
            grouped[theme]['repeat']
            / max(1, grouped[theme]['answered'] + grouped[theme]['repeat']),
            grouped[theme]['answered'] + grouped[theme]['repeat'],
        ),
        reverse=True,
    )
    answered_values = []
    repeat_values = []
    labels = []
    for theme in themes:
        total = grouped[theme]['answered'] + grouped[theme]['repeat']
        labels.append(f'{_shorten(theme, 30)} · {total}')
        answered_values.append(round(grouped[theme]['answered'] / total * 100))
        repeat_values.append(100 - answered_values[-1])

    chart = _chart(
        labels,
        [
            {
                'label': 'Отвечено',
                'data': answered_values,
                'backgroundColor': CHART_COLORS['success'],
                'suffixYAxis': '%',
            },
            {
                'label': 'На повторение',
                'data': repeat_values,
                'backgroundColor': CHART_COLORS['warning'],
            },
        ],
        options={
            'indexAxis': 'y',
            'scales': {
                'x': {'stacked': True, 'beginAtZero': True, 'max': 100},
                'y': {'stacked': True},
            },
        },
    )
    total_answered = sum(item['answered'] for item in grouped.values())
    total_questions = sum(
        item['answered'] + item['repeat'] for item in grouped.values()
    )
    answered_percent = (
        round(total_answered / total_questions * 100) if total_questions else None
    )
    return chart, answered_percent


def _item(obj, title, subtitle, now, moment=None, tone='warning'):
    return {
        'title': title,
        'subtitle': subtitle,
        'age': _age_label(moment, now),
        'url': _admin_url(type(obj), 'change', obj.pk),
        'tone': tone,
    }


def _attention_sections(student_ids, group_ids, now):
    pending = (
        LessonSolution.objects
        .filter(student_id__in=student_ids, status=LessonSolution.Status.PENDING)
        .select_related('student__user', 'schedule')
        .order_by('updated_at')
    )
    revision_limit = now - timedelta(days=7)
    revisions = (
        LessonSolution.objects
        .filter(
            student_id__in=student_ids,
            status=LessonSolution.Status.NEEDS_REVISION,
            updated_at__lte=revision_limit,
        )
        .select_related('student__user', 'schedule')
        .order_by('updated_at')
    )
    projects = (
        ProjectForReview.objects
        .filter(user_id__in=student_ids, status=False)
        .select_related('user__user', 'category')
        .order_by('created_at')
    )
    failed_ai = (
        CodeReview.objects
        .filter(
            project__user_id__in=student_ids,
            ai_generation_status='failed',
        )
        .select_related('project__user__user')
        .order_by('created_at')
    )
    ready_ai = (
        CodeReview.objects
        .filter(
            project__user_id__in=student_ids,
            ai_generation_status='ready',
            approved_at__isnull=True,
        )
        .select_related('project__user__user')
        .order_by('created_at')
    )
    questions = (
        StudentQuestion.objects
        .filter(group_id__in=group_ids, solved=False)
        .select_related('group')
        .order_by('created_at')
    )
    applications = (
        ApplicationsForTraining.objects
        .filter(descry=False)
        .select_related('student__user')
        .order_by('created_at')
    )

    return [
        {
            'title': 'Решения на проверке',
            'count': pending.count(),
            'url': f'{_admin_url(LessonSolution)}?status__exact=pending',
            'items': [
                _item(
                    solution,
                    str(solution.student),
                    solution.schedule.theme,
                    now,
                    solution.updated_at,
                )
                for solution in pending[:4]
            ],
        },
        {
            'title': 'Доработка больше 7 дней',
            'count': revisions.count(),
            'url': f'{_admin_url(LessonSolution)}?status__exact=needs_revision',
            'items': [
                _item(
                    solution,
                    str(solution.student),
                    solution.schedule.theme,
                    now,
                    solution.updated_at,
                    'danger',
                )
                for solution in revisions[:4]
            ],
        },
        {
            'title': 'Проекты ожидают ревью',
            'count': projects.count(),
            'url': _admin_url(ProjectForReview),
            'items': [
                _item(
                    project,
                    str(project.user),
                    str(project.category),
                    now,
                    project.created_at,
                )
                for project in projects[:4]
            ],
        },
        {
            'title': 'Черновики ИИ',
            'count': failed_ai.count() + ready_ai.count(),
            'url': _admin_url(CodeReview),
            'items': [
                *[
                    _item(
                        review,
                        str(review.project.user),
                        'Ошибка генерации черновика',
                        now,
                        review.created_at,
                        'danger',
                    )
                    for review in failed_ai[:2]
                ],
                *[
                    _item(
                        review,
                        str(review.project.user),
                        'Черновик готов к согласованию',
                        now,
                        review.created_at,
                        'warning',
                    )
                    for review in ready_ai[:2]
                ],
            ],
        },
        {
            'title': 'Нерешённые вопросы',
            'count': questions.count(),
            'url': _admin_url(StudentQuestion),
            'items': [
                _item(
                    question,
                    question.group.title,
                    _shorten(question.question, 64),
                    now,
                    question.created_at,
                )
                for question in questions[:4]
            ],
        },
        {
            'title': 'Новые заявки',
            'count': applications.count(),
            'url': _admin_url(ApplicationsForTraining),
            'items': [
                _item(
                    application,
                    str(application.student),
                    'Заявка на обучение',
                    now,
                    application.created_at,
                )
                for application in applications[:4]
            ],
        },
    ]


def dashboard_callback(request, context):
    """Добавляет в Unfold только учебные и операционные показатели."""
    now = timezone.now()
    period_days = _period(request)
    start = now - timedelta(days=period_days)
    groups, selected_group_id, students = _scope(request)
    student_rows = list(students.values('pk', 'user_id', 'groups_id'))
    student_ids = [student['pk'] for student in student_rows]
    student_user_ids = [student['user_id'] for student in student_rows]
    group_ids = sorted({student['groups_id'] for student in student_rows})

    solution_chart = _solution_activity(student_ids, start, now)
    status_chart, status_totals = _solution_statuses(student_ids)
    completions, answers = _completed_answer_rows(student_user_ids, start)
    quiz_chart, _ = _quiz_results(completions, answers)
    difficult_chart = _difficult_questions(answers)
    quiz_activity_chart = _quiz_activity(completions, start, now)
    interview_chart, interview_answered_percent = _interview_progress(
        student_user_ids,
    )
    pending_reviews = ProjectForReview.objects.filter(
        user_id__in=student_ids,
        status=False,
    ).count()
    average_quiz_result = (
        round(sum(int(answer['is_correct']) for answer in answers) / len(answers) * 100)
        if answers
        else None
    )

    context.update({
        'dashboard_period': period_days,
        'dashboard_periods': PERIODS,
        'dashboard_groups': groups,
        'dashboard_group_id': selected_group_id,
        'dashboard_group_ids': group_ids,
        'dashboard_kpis': [
            {
                'title': 'Активных учеников',
                'value': len(student_ids),
                'label': 'в выбранных группах',
                'icon': 'school',
                'url': _admin_url(Student),
            },
            {
                'title': 'На проверке',
                'value': status_totals.get(LessonSolution.Status.PENDING, 0),
                'label': 'решений учеников',
                'icon': 'rate_review',
                'url': f'{_admin_url(LessonSolution)}?status__exact=pending',
            },
            {
                'title': 'Нужна доработка',
                'value': status_totals.get(
                    LessonSolution.Status.NEEDS_REVISION,
                    0,
                ),
                'label': 'текущий статус',
                'icon': 'build',
                'url': (
                    f'{_admin_url(LessonSolution)}?'
                    'status__exact=needs_revision'
                ),
            },
            {
                'title': 'Прохождений опросов',
                'value': len(completions),
                'label': f'за {period_days} дней',
                'icon': 'quiz',
                'url': _admin_url(PassedPolls),
            },
            {
                'title': 'Средний результат',
                'value': (
                    f'{average_quiz_result}%'
                    if average_quiz_result is not None
                    else '—'
                ),
                'label': 'по завершённым опросам',
                'icon': 'analytics',
                'url': _admin_url(PassedPolls),
            },
            {
                'title': 'Ожидают ревью',
                'value': pending_reviews,
                'label': 'проектов учеников',
                'icon': 'code',
                'url': _admin_url(ProjectForReview),
            },
        ],
        'solution_activity_chart': solution_chart,
        'solution_status_chart': status_chart,
        'quiz_results_chart': quiz_chart,
        'difficult_questions_chart': difficult_chart,
        'quiz_activity_chart': quiz_activity_chart,
        'interview_progress_chart': interview_chart,
        'interview_answered_percent': interview_answered_percent,
        'attention_sections': _attention_sections(
            student_ids,
            group_ids,
            now,
        ),
    })
    return context
