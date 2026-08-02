from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from Course.models import Student
from interview.answer import get_questions
from interview.models import InterviewQuestionCategory, InterviewQuestion


def parse_integer(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@login_required
def test_answer(request):
    student = Student.objects.filter(name=request.user.username).first()
    if not student or not student.is_learned:
        return redirect('home')

    amount = parse_integer(request.GET.get('amount'), 0)
    categories = InterviewQuestionCategory.objects.all()
    if not (10 <= amount <= 50):
        return render(request, 'interview/index.html',
                      {'categories': categories})

    selected_technologies = request.GET.getlist('technologies')
    random_mode = (
        not selected_technologies or 'random' in selected_technologies
    )
    technologies = (
        [category.title for category in categories]
        if random_mode
        else selected_technologies
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
        questions = InterviewQuestion.objects.filter(complexity__gte=start,
                                                     complexity__lte=end).all()
    else:
        start, end = 1, 3
        questions = InterviewQuestion.objects.all()

    question = InterviewQuestion.objects.filter(title__in=get_questions(
        questions,
        technologies,
        amount))
    return render(request, 'interview/questions.html',
                  {'question': question, 'amount': amount,
                   'technologies': technologies,
                   'categories': [i.title for i in categories],
                   'start': start,
                   'end': end,
                   'random_mode': random_mode})
