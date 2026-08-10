from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from Course.models import Student
from interview.answer import get_questions, mark_questions_as_shown
from interview.models import (
    InterviewQuestion,
    InterviewQuestionCategory,
    InterviewQuestionProgress,
)


ANSWERED_COOLDOWN_DAYS = 14


def parse_integer(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@login_required
def test_answer(request):
    student = Student.objects.for_user(request.user)
    if not student or not student.is_learned:
        return redirect('home')

    amount = parse_integer(request.GET.get('amount'), 0)
    categories = InterviewQuestionCategory.objects.all()
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
