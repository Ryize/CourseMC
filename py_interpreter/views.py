from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def py_interpreter(request):
    return render(request, 'py_interpreter/py_interpreter.html')
