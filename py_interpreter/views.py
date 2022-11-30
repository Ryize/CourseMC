from django.shortcuts import render

from reviews.models import Review


def py_interpreter(request):
    data = {"reviews_count": Review.objects.all().count()}
    return render(request, "py_interpreter/py_interpreter.html", data)
