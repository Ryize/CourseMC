from typing import Union

from django.contrib import messages
from django.forms import ModelForm
from django.http import HttpResponseRedirect, HttpResponseNotFound, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from questionnaire.models import Quiz, Question


def process_form(
    request,
    form: ModelForm,
    id: Union[None, int] = None,
    message_success: str = "Вы создали вопрос!",
    message_error: str = "Хм, что-то не то!",
    func_redirect: str = "create_question",
) -> HttpResponseRedirect:
    """
    Проверяет форму, выводит сообщение ошибки/успеха в случае валидности (не) формы.
    :param form: Форма для проверки
    :param id: Если редирект на путь, требующий GET параметр
    :param message_success: Сообщение (flash) в случае валидности формы
    :param message_error: Сообщение (flash) в случае не валидности формы
    :param func_redirect: View на которую произойдёт редирект
    :return: HttpResponseRedirect (готовый путь для редиректа, генерируется с помощью django.shortcuts.redirect)
    """
    if form.is_valid():
        form.save()
        messages.info(request, message_success)
        if not id:
            return redirect(func_redirect)
        return redirect(func_redirect, id)
    messages.error(request, message_error)
    if not id:
        return redirect(func_redirect)
    return redirect(func_redirect, id)


def _check_poll_lifetime(poll: Quiz) -> Union[bool, HttpResponseNotFound]:
    """
    Проверяет не кончился ли срок жизни опроса.
    :param poll: Опрос, который будет проверен
    :return: Union[bool, HttpResponseNotFound] (True - если опрос не кончился,
                                                HttpResponseNotFound - если срок действия опроса истёк)
    """
    date_now = timezone.now()
    date_now.astimezone(timezone.utc).replace(tzinfo=None)
    if poll.lifetime <= date_now:
        return HttpResponseNotFound("Срок действия опроса истёк!")
    return True


def get_standart_render(request, poll: Quiz, question: Question) -> HttpResponse:
    """Возвращает стандартную страницу для ответа на вопрос в опросе."""
    context = {
        "poll": poll,
        "question": question,
    }
    return render(request, "questionnaire/take_poll.html", context)
