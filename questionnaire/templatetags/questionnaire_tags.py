from django import template
from collections import Counter
from django.db.models import Avg

from questionnaire.models import Quiz

register = template.Library()


@register.filter(name='statistic')
def get_statistic(poll, user_id):
    user_quiz = poll.user_quiz.all()
    wrong_answer = [i.answers for i in user_quiz if not i.answers.correct]
    result_number = round((len(user_quiz) - len(wrong_answer)) / len(user_quiz) * 100, 1)
    result = f'<span style="color: green;">{result_number}%</span>'
    if result_number == 0:
        result = '<span style="color: red;">нет</span>'
    elif result_number < 26:
        result = f'<span style="color: red;">{result_number}%</span>'
    elif result_number < 50:
        result = f'<span style="color: Goldenrod;">{result_number}%</span>'
    elif result_number < 76:
        result = f'<span style="color: PaleGreen;">{result_number}%</span>'
    rating_number = 0
    for i in poll.rating.all():
        rating_number += i.answer_number
    try:
        avg_rating = f'<br>Средняя оценка: {rating_number / poll.rating.count()}/5<br'
    except:
        avg_rating = ''
    try:
        answer_with_most_errors = list(reversed(sorted(Counter(wrong_answer).items(), key=lambda x: x[1])))[0]
        return f'Правильных ответов: <strong>{result}</strong><br>Больше всего ошибок ({answer_with_most_errors[1]}): {answer_with_most_errors[0].question}<br>{avg_rating}'
    except:
        return f'Правильных ответов: <strong>{result}</strong>{avg_rating}'

