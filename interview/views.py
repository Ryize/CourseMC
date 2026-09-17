from datetime import timedelta
import os

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from Course.models import Student
from interview.ai_analysis import (
    MockInterviewAnalysisError,
    analyze_mock_interview,
    mark_analysis_failed,
)
from interview.answer import get_questions, mark_questions_as_shown
from interview.forms import MockInterviewStartForm, MockLiveCodingForm
from interview.mock_interview import (
    create_mock_interview,
    mock_interview_availability,
)
from interview.models import (
    InterviewQuestion,
    InterviewQuestionCategory,
    InterviewQuestionProgress,
    MockInterview,
    MockInterviewAnswer,
    MockInterviewFile,
)


ANSWERED_COOLDOWN_DAYS = 14
MAX_THEORY_ANSWER_LENGTH = 8_000
CATEGORY_POPULARITY_ORDER = (
    'HR’ские',
    'Python',
    'ООП',
    'Django',
    'FastAPI',
    'Flask',
    'Базы данных',
    'SQL',
    'HTTP / API',
    'Веб-разработка',
    'Алгоритмы, структуры',
    'Асинхронность',
    'ORM',
    'Тестирование',
    'Best Practices',
    'Tools',
    'GIL',
    'Модули / Пакеты',
    'Языки',
    'Процессы в компании',
    'Общая разработка',
)


def parse_integer(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def ordered_interview_categories():
    """Популярные темы первыми, остальные — по алфавиту."""
    priority = Case(
        *(
            When(title=title, then=Value(position))
            for position, title in enumerate(CATEGORY_POPULARITY_ORDER)
        ),
        default=Value(len(CATEGORY_POPULARITY_ORDER)),
        output_field=IntegerField(),
    )
    return InterviewQuestionCategory.objects.alias(
        popularity_order=priority,
    ).order_by('popularity_order', 'title')


def _active_student(request):
    student = Student.objects.for_user(request.user)
    return student if student and student.is_learned else None


def _owned_interview(request, interview_id):
    return get_object_or_404(
        MockInterview.objects.prefetch_related('frameworks', 'answers'),
        pk=interview_id,
        user=request.user,
    )


def _teacher_can_view_interview(user, interview):
    if user.is_superuser:
        return True
    if not user.is_staff:
        return False
    return Student.objects.filter(
        user=interview.user,
        groups__teacher__user=user,
    ).exists()


def _private_file_response(field_file, filename):
    response = FileResponse(
        field_file.open('rb'),
        as_attachment=True,
        filename=filename,
    )
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def test_answer(request):
    if not _active_student(request):
        return redirect('home')

    amount = parse_integer(request.GET.get('amount'), 0)
    categories = ordered_interview_categories()
    if not (10 <= amount <= 50):
        return render(request, 'interview/index.html',
                      {'categories': categories})

    category_titles = [category.title for category in categories]
    selected_technologies = [
        technology for technology in request.GET.getlist('technologies')
        if technology in category_titles
    ]
    # «Случайные» не должны расширять конкретно выбранную категорию.
    random_mode = not selected_technologies
    technologies = category_titles if random_mode else selected_technologies

    questions = InterviewQuestion.objects.filter(
        theme__title__in=technologies,
    )
    if not random_mode and 'Python' in technologies:
        start = parse_integer(request.GET.get('start'), None)
        end = parse_integer(request.GET.get('end'), None)
        if (
            start is None
            or end is None
            or not (1 <= start <= end <= 10)
        ):
            start, end = 1, 3
        questions = questions.filter(
            Q(
                theme__title='Python',
                complexity__gte=start,
                complexity__lte=end,
            ) | ~Q(theme__title='Python')
        )
    else:
        start, end = 1, 3
    questions = questions.select_related('theme')

    question = get_questions(
        questions,
        technologies,
        amount,
        user=request.user,
    )
    mark_questions_as_shown(request.user, question)
    return render(request, 'interview/questions.html',
                  {'question': question, 'amount': amount,
                   'technologies': technologies,
                   'categories': [i.title for i in categories],
                   'start': start,
                   'end': end,
                   'random_mode': random_mode})


@login_required
@require_POST
def question_progress(request, question_id):
    """Сохраняет самооценку только для вопроса, ранее выданного пользователю."""
    student = Student.objects.for_user(request.user)
    if not student or not student.is_learned:
        raise PermissionDenied

    action = request.POST.get('action')
    status_by_action = {
        'answered': InterviewQuestionProgress.Status.ANSWERED,
        'repeat': InterviewQuestionProgress.Status.REPEAT,
    }
    if action not in status_by_action:
        return JsonResponse({'error': 'Неизвестное действие.'}, status=400)

    with transaction.atomic():
        progress = get_object_or_404(
            InterviewQuestionProgress.objects.select_for_update(),
            user=request.user,
            question_id=question_id,
        )
        now = timezone.now()
        progress.status = status_by_action[action]
        progress.next_available_at = (
            now + timedelta(days=ANSWERED_COOLDOWN_DAYS)
            if action == 'answered'
            else now
        )
        progress.save(update_fields=('status', 'next_available_at', 'updated_at'))
    return JsonResponse({
        'status': progress.status,
        'next_available_at': progress.next_available_at.isoformat(),
    })


@login_required
def mock_interview_start(request):
    if not _active_student(request):
        return redirect('home')

    active = (
        MockInterview.objects
        .filter(
            user=request.user,
            status__in=(
                MockInterview.Status.THEORY,
                MockInterview.Status.LIVE_CODING,
                MockInterview.Status.ANALYZING,
                MockInterview.Status.FAILED,
            ),
        )
        .prefetch_related('frameworks')
        .order_by('-started_at')
        .first()
    )
    availability = mock_interview_availability(request.user)
    if request.method == 'POST':
        if active:
            return redirect('mock_interview_resume', interview_id=active.pk)
        form = MockInterviewStartForm(request.POST)
        if form.is_valid():
            try:
                interview = create_mock_interview(
                    request.user,
                    form.cleaned_data['frameworks'],
                    form.cleaned_data['level'],
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return redirect('mock_interview_theory', interview_id=interview.pk)
    else:
        form = MockInterviewStartForm()

    recent_history = (
        MockInterview.objects
        .filter(user=request.user, status=MockInterview.Status.COMPLETED)
        .prefetch_related('frameworks')[:3]
    )
    return render(request, 'interview/mock_start.html', {
        'form': form,
        'active_interview': active,
        'availability': availability,
        'history': recent_history,
    })


@login_required
def mock_interview_history(request):
    if not _active_student(request):
        return redirect('home')
    history = (
        MockInterview.objects
        .filter(user=request.user, status=MockInterview.Status.COMPLETED)
        .prefetch_related('frameworks')
    )
    return render(request, 'interview/mock_history.html', {
        'history': history,
    })


@login_required
def mock_interview_resume(request, interview_id):
    interview = _owned_interview(request, interview_id)
    route_by_status = {
        MockInterview.Status.THEORY: 'mock_interview_theory',
        MockInterview.Status.LIVE_CODING: 'mock_interview_live_coding',
        MockInterview.Status.ANALYZING: 'mock_interview_processing',
        MockInterview.Status.FAILED: 'mock_interview_processing',
        MockInterview.Status.COMPLETED: 'mock_interview_result',
    }
    route = route_by_status.get(interview.status, 'mock_interview_start')
    if route == 'mock_interview_start':
        return redirect(route)
    return redirect(route, interview_id=interview.pk)


@login_required
@require_POST
def mock_interview_abandon(request, interview_id):
    interview = _owned_interview(request, interview_id)
    if interview.status in (
        MockInterview.Status.THEORY,
        MockInterview.Status.LIVE_CODING,
        MockInterview.Status.FAILED,
    ):
        interview.status = MockInterview.Status.ABANDONED
        interview.save(update_fields=('status', 'updated_at'))
    return redirect('mock_interview_start')


@login_required
def mock_interview_theory(request, interview_id):
    if not _active_student(request):
        return redirect('home')
    interview = _owned_interview(request, interview_id)
    if interview.status != MockInterview.Status.THEORY:
        return redirect('mock_interview_resume', interview_id=interview.pk)

    answers = list(interview.answers.all())
    error = ''
    if request.method == 'POST':
        for answer in answers:
            value = request.POST.get(f'answer_{answer.pk}', '').strip()
            answer.answer_text = value[:MAX_THEORY_ANSWER_LENGTH]
        if any(not answer.answer_text for answer in answers):
            error = 'Ответьте на все вопросы перед переходом к лайвкодингу.'
        else:
            with transaction.atomic():
                MockInterviewAnswer.objects.bulk_update(answers, ('answer_text',))
                interview.status = MockInterview.Status.LIVE_CODING
                interview.theory_completed_at = timezone.now()
                interview.save(update_fields=(
                    'status', 'theory_completed_at', 'updated_at',
                ))
            return redirect('mock_interview_live_coding', interview_id=interview.pk)

    sections = []
    for section_value, section_title in MockInterviewAnswer.Section.choices:
        section_answers = [item for item in answers if item.section == section_value]
        if section_answers:
            sections.append((section_title, section_answers))
    return render(request, 'interview/mock_theory.html', {
        'interview': interview,
        'sections': sections,
        'error': error,
    })


@login_required
def mock_interview_live_coding(request, interview_id):
    if not _active_student(request):
        return redirect('home')
    interview = _owned_interview(request, interview_id)
    if interview.status != MockInterview.Status.LIVE_CODING:
        return redirect('mock_interview_resume', interview_id=interview.pk)

    if request.method == 'POST':
        form = MockLiveCodingForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                interview.live_coding_answer = form.cleaned_data['solution'].strip()
                interview.live_coding_repository_url = (
                    form.cleaned_data['repository_url'].strip()
                )
                interview.status = MockInterview.Status.ANALYZING
                interview.ai_error = ''
                interview.analysis_started_at = None
                interview.save(update_fields=(
                    'live_coding_answer', 'live_coding_repository_url',
                    'status', 'ai_error',
                    'analysis_started_at', 'updated_at',
                ))
                for uploaded_file in form.cleaned_data['files']:
                    MockInterviewFile.objects.create(
                        interview=interview,
                        file=uploaded_file,
                        original_name=os.path.basename(uploaded_file.name)[:255],
                    )
            return redirect('mock_interview_processing', interview_id=interview.pk)
    else:
        form = MockLiveCodingForm(initial={
            'solution': interview.live_coding_answer,
            'repository_url': interview.live_coding_repository_url,
        })
    return render(request, 'interview/mock_live_coding.html', {
        'interview': interview,
        'form': form,
    })


@login_required
@ensure_csrf_cookie
def mock_interview_processing(request, interview_id):
    interview = _owned_interview(request, interview_id)
    if interview.status == MockInterview.Status.COMPLETED:
        return redirect('mock_interview_result', interview_id=interview.pk)
    if interview.status not in (
        MockInterview.Status.ANALYZING,
        MockInterview.Status.FAILED,
    ):
        return redirect('mock_interview_resume', interview_id=interview.pk)
    return render(request, 'interview/mock_processing.html', {
        'interview': interview,
    })


@login_required
@require_POST
def mock_interview_analyze(request, interview_id):
    interview = _owned_interview(request, interview_id)
    if interview.status == MockInterview.Status.COMPLETED:
        return JsonResponse({
            'redirect_url': reverse('mock_interview_result', args=(interview.pk,)),
        })
    if interview.status not in (
        MockInterview.Status.ANALYZING,
        MockInterview.Status.FAILED,
    ):
        return JsonResponse({'error': 'Собеседование ещё не готово к анализу.'}, status=409)

    with transaction.atomic():
        locked = MockInterview.objects.select_for_update().get(pk=interview.pk)
        now = timezone.now()
        if (
            locked.analysis_started_at
            and locked.status == MockInterview.Status.ANALYZING
            and locked.analysis_started_at > now - timedelta(minutes=3)
        ):
            return JsonResponse({'error': 'Анализ уже выполняется.'}, status=409)
        locked.status = MockInterview.Status.ANALYZING
        locked.analysis_started_at = now
        locked.ai_error = ''
        locked.save(update_fields=(
            'status', 'analysis_started_at', 'ai_error', 'updated_at',
        ))

    try:
        analyze_mock_interview(locked)
    except MockInterviewAnalysisError as error:
        mark_analysis_failed(locked, error)
        return JsonResponse({'error': str(error)}, status=502)
    return JsonResponse({
        'redirect_url': reverse('mock_interview_result', args=(interview.pk,)),
    })


@login_required
def mock_interview_result(request, interview_id):
    interview = _owned_interview(request, interview_id)
    if interview.status != MockInterview.Status.COMPLETED:
        return redirect('mock_interview_resume', interview_id=interview.pk)
    sections = []
    answers = list(interview.answers.all())
    for section_value, section_title in MockInterviewAnswer.Section.choices:
        section_answers = [item for item in answers if item.section == section_value]
        if section_answers:
            sections.append((section_title, section_answers))
    return render(request, 'interview/mock_result.html', {
        'interview': interview,
        'sections': sections,
    })


@login_required
def mock_task_file_download(request, interview_id):
    interview = get_object_or_404(
        MockInterview.objects.select_related('live_coding_task', 'user'),
        pk=interview_id,
    )
    if request.user != interview.user and not _teacher_can_view_interview(
        request.user,
        interview,
    ):
        raise PermissionDenied
    task = interview.live_coding_task
    if not task or not task.starter_file:
        return JsonResponse({'error': 'У задания нет файла.'}, status=404)
    return _private_file_response(
        task.starter_file,
        os.path.basename(task.starter_file.name),
    )


@login_required
def mock_solution_file_download(request, file_id):
    solution_file = get_object_or_404(
        MockInterviewFile.objects.select_related('interview__user'),
        pk=file_id,
    )
    interview = solution_file.interview
    if request.user != interview.user and not _teacher_can_view_interview(
        request.user,
        interview,
    ):
        raise PermissionDenied
    return _private_file_response(solution_file.file, solution_file.original_name)
