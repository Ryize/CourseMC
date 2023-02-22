from typing import Union

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (HttpResponseNotFound)
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from .forms import AnswerForm, QuestionForm, QuizForm
from .models import (AnswerQuestion, PassedPolls, Question, Quiz, Rating,
                     UserAnswer)
from .service import process_form, _check_poll_lifetime, get_standart_render


class QuizListView(ListView):
    model = Quiz
    template_name = "questionnaire/my_poll.html"
    context_object_name = "my_polls"
    paginate_by = 16

    def get_queryset(self):
        if self.request.user.is_authenticated:
            my_polls = (
                Quiz.objects.filter(user=self.request.user)
                .order_by("-created_at")
                .prefetch_related()
            )
            return my_polls

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context["UserAnswer"] = UserAnswer
        context["PassedPolls"] = PassedPolls

        return context

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if request.method.lower() in self.http_method_names:
            handler = getattr(
                self, request.method.lower(), self.http_method_not_allowed
            )
        else:
            handler = self.http_method_not_allowed
        return handler(request, *args, **kwargs)


def index(request):
    return render(request, "questionnaire/index.html")


@login_required
def create_poll(request):
    if request.method == "GET":
        context = {"form": QuizForm()}
        return render(request, "questionnaire/create_poll.html", context)
    form = QuizForm(request.POST)
    if form.is_valid():
        form_with_user = form.save(commit=False)
        form_with_user.user = request.user
        form_with_user.save()
        messages.success(request, "Вы успешно создали опрос!")
        return redirect("create_question", form_with_user.pk)
    messages.error(request, "Хм, что-то не то!")
    return redirect("create_poll")


@login_required
def create_question(request, quiz_id):
    quiz = Quiz.objects.filter(pk=quiz_id).all()
    if request.method == "GET":
        context = {
            "form": QuestionForm(quiz),
        }
        return render(request, "questionnaire/create_question.html", context)
    form = QuestionForm(None, request.POST)
    return process_form(request, form, quiz_id)


@login_required
def create_answer(request):
    if request.method == "GET":
        context = {"form": AnswerForm()}
        return render(request, "questionnaire/create_answer.html", context)
    form = AnswerForm(request.POST)
    return process_form(
        request,
        form,
        message_success="Вы создали ответ на вопрос!",
        func_redirect="create_answer",
    )


@login_required
def my_poll(request):
    my_polls = (
        Quiz.objects.filter(user=request.user)
        .order_by("-created_at")
        .prefetch_related()
    )
    context = {
        "my_polls": my_polls,
        "UserAnswer": UserAnswer,
        "PassedPolls": PassedPolls,
    }
    return render(request, "questionnaire/my_poll.html", context)


@login_required
def go_poll(request):
    if request.method == "GET":
        return render(request, "questionnaire/go_poll.html")
    if not request.POST.get("poll_id") or not request.POST.get("poll_id").isdigit():
        messages.error(request, "Значение поля id опроса не корректно!")
        return render(request, "questionnaire/go_poll.html")
    return redirect("take_poll", request.POST.get("poll_id"))


@login_required
def take_poll(request, poll_id):
    try:
        poll = Quiz.objects.get(pk=poll_id)
    except Quiz.DoesNotExist:
        messages.error(request, "Вы указали не верный id опроса!")
        return redirect("go_poll")
    question = check_possibility_passing_poll(request, poll)
    if isinstance(question, HttpResponseNotFound):
        return question
    if request.method == "GET":
        return get_standart_render(request, poll, question)
    number_question = request.POST.get("number_question")
    answers = request.POST.get("answers")

    all_question = poll.questions.all()
    # Обрабатываем кнопку "Назад". Если нажата, возвращаем предыдущий вопрос
    if request.POST.get("redirect") and number_question:
        question = all_question.filter(pk=int(number_question)).first()
        return get_standart_render(request, poll, question)

    if not (number_question and answers):
        messages.error(request, "Вы передали не все параметры!")
        return get_standart_render(request, poll, question)

    for i in request.POST.lists():
        answers = (
            i[1] if i[0] == "answers" else []
        )  # Получаем ответ, который дал пользователь
    try:
        UserAnswer.objects.get(
            quiz=poll,
            question=get_object_or_404(Question, pk=int(number_question)),
            user=request.user,
        ).delete()
    except:
        pass
    answer = UserAnswer(
        quiz=poll,
        question=get_object_or_404(Question, pk=int(number_question)),
        answers=AnswerQuestion.objects.filter(pk=int(answers[0]))[0],
        user=request.user,
    )
    answer.save()

    number_iter = 1
    while True:
        question = all_question.filter(pk=int(number_question) + number_iter).first()

        # Проверяем, есть ли вопрос, если нет, то сообщаем об успешном прохождении опроса
        if not question:
            passed_quiz = PassedPolls(quiz=poll, passed_user=request.user)
            passed_quiz.save()
            messages.info(request, "Вы успешно прошли опрос!")
            return redirect("rating", poll_id)
        if not question.answers.all():
            number_iter += 1
            continue
        break
    return get_standart_render(request, poll, question)


@login_required
def rating(request, poll_id: int):
    quiz = Quiz.objects.filter(pk=poll_id).first()
    if not quiz or not PassedPolls.objects.filter(passed_user=request.user).first():
        return HttpResponseNotFound("Указанный опрос не найден или вы его не прошли!")
    if request.method == "POST":
        try:
            rating_quiz = Rating.objects.get(user=request.user, quiz=quiz)
            rating_quiz.delete()
            rating_quiz = Rating(
                answer_number=request.POST.get("rating"),
                comment=request.POST.get("comment"),
                quiz=quiz,
                user=request.user,
            )
            rating_quiz.save()
            messages.success(request, "Вы успешно оставили отзыв!")
        except:
            pass
        finally:
            return redirect("questionnaireIndex")
    context = {"poll": quiz}
    return render(request, "questionnaire/rating.html", context)


def check_possibility_passing_poll(
    request, poll: Quiz
) -> Union[Question, HttpResponseNotFound]:
    """
    Используется для проверки возможности пройти определённый опрос пользователем.
    request: WSGIRequest
    return: Question (вопрос на который пользователь будет отвечать)
            or HttpResponseNotFound (сообщение о невозможности пройти опрос).
    """
    check_poll_lifetime = _check_poll_lifetime(poll)
    if not isinstance(check_poll_lifetime, bool):
        return check_poll_lifetime
    if PassedPolls.objects.filter(quiz=poll, passed_user=request.user):
        return HttpResponseNotFound("Вы уже прошли этот опрос!")
    for question in poll.questions.all():
        if len(question.answers.all()) > 0:
            return question
    return HttpResponseNotFound("В этом опросе нет вопросов с ответами")
