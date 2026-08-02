from collections import Counter

from django import template
register = template.Library()


@register.filter(name="statistic")
def get_statistic(poll, user_id):
    user_quiz = poll.user_quiz.all()
    if not user_quiz:
        return "На вопросы пока никто не ответил."

    wrong_answer = [i.answers for i in user_quiz if not i.answers.correct]
    result_number = round(
        (len(user_quiz) - len(wrong_answer)) / len(user_quiz) * 100, 1
    )
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
    if poll.rating.count():
        avg_rating = f"<br>Средняя оценка: {rating_number / poll.rating.count()}/5<br"
    else:
        avg_rating = ""

    if not wrong_answer:
        return f"Правильных ответов: <strong>{result}</strong>{avg_rating}"

    answer_with_most_errors = Counter(wrong_answer).most_common(1)[0]
    return (
        f"Правильных ответов: <strong>{result}</strong><br>"
        f"Больше всего ошибок ({answer_with_most_errors[1]}): "
        f"{answer_with_most_errors[0].question}<br>{avg_rating}"
    )
