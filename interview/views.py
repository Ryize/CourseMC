from django.shortcuts import render
from interview.answer import get_questions
from interview.models import InterviewQuestionCategory, InterviewQuestion


def test_answer(request):
    amount = int(request.GET.get('amount', 0))
    categories = InterviewQuestionCategory.objects.all()
    if not (10 <= amount <= 50):
        return render(request, 'interview/index.html',
                      {'categories': categories})
    technologies = request.GET.getlist('technologies')
    if not technologies or technologies.count('random'):
        technologies = [i.title for i in categories]
    question = get_questions(
        InterviewQuestion.objects.all(),
        technologies,
        amount)
    return render(request, 'interview/questions.html',
                  {'question': question, 'amount': amount,
                   'technologies': technologies,
                   'categories': [i.title for i in categories]})
