import random

from django.db.models import QuerySet


def get_questions(data: QuerySet, themes: QuerySet, amount: int):
    theme, percent = [], []
    for i in data:
        if str(i.theme) in themes:
            theme.append(i.title)
            percent.append(int(i.percent) * 2)
    answers = []
    for i in range(amount):
        if not theme:
            break
        answer = random.choices(theme, weights=percent)[0]
        answers.append(answer)
        del percent[theme.index(answer)]
        theme.pop(theme.index(answer))
    return answers
