from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from Course.models import Student
from interview.answer import get_questions
from interview.models import InterviewQuestionCategory, InterviewQuestion


@login_required
def test_answer(request):
    student = Student.objects.filter(name=request.user.username).first()
    if not student or not student.is_learned:
        return redirect('home')
    amount = int(request.GET.get('amount', 0))
    categories = InterviewQuestionCategory.objects.all()
    if not (10 <= amount <= 50):
        return render(request, 'interview/index.html',
                      {'categories': categories})
    technologies = request.GET.getlist('technologies')
    if not technologies or technologies.count('random'):
        technologies = [i.title for i in categories]
    if 'Python' in technologies:
        start = int(request.GET.get('start', 1))
        end = int(request.GET.get('end', 3))
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
                   'end': end})
