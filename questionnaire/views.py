from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from .forms import AnswerForm, QuestionForm, QuizForm
from .models import (
    AnswerQuestion,
    PassedPolls,
    Question,
    Quiz,
    Rating,
    UserAnswer,
)
from .service import poll_is_active


class QuizListView(LoginRequiredMixin, ListView):
    model = Quiz
    template_name = "questionnaire/my_poll.html"
    context_object_name = "my_polls"
    paginate_by = 16

    def get_queryset(self):
        return (
            Quiz.objects
            .filter(user=self.request.user)
            .order_by("-created_at")
            .prefetch_related(
                "questions__answers",
                "passed_quiz__passed_user",
                "user_quiz__answers",
                "rating",
            )
        )


def index(request):
    return render(request, "questionnaire/index.html")


@login_required
def create_poll(request):
    form = QuizForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        quiz = form.save(commit=False)
        quiz.user = request.user
        quiz.save()
        messages.success(request, "Вы успешно создали опрос!")
        return redirect("create_question", quiz.pk)

    return render(request, "questionnaire/create_poll.html", {"form": form})


@login_required
def create_question(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    form = QuestionForm(quiz, request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.info(request, "Вы создали вопрос!")
        return redirect("create_question", quiz.pk)

    return render(
        request,
        "questionnaire/create_question.html",
        {"form": form, "quiz": quiz},
    )


@login_required
def create_answer(request):
    form = AnswerForm(request.user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.info(request, "Вы создали ответ на вопрос!")
        return redirect("create_answer")

    return render(request, "questionnaire/create_answer.html", {"form": form})


@login_required
def go_poll(request):
    if request.method == "GET":
        return render(request, "questionnaire/go_poll.html")

    poll_id = request.POST.get("poll_id", "")
    if not poll_id.isdigit():
        messages.error(request, "Значение поля id опроса некорректно!")
        return render(request, "questionnaire/go_poll.html")

    return redirect("take_poll", int(poll_id))


def available_questions(poll):
    return list(
        poll.questions
        .filter(answers__isnull=False)
        .distinct()
        .prefetch_related("answers")
        .order_by("pk")
    )


def render_question(request, poll, questions, question):
    index = questions.index(question)
    previous_question = questions[index - 1] if index > 0 else None
    return render(
        request,
        "questionnaire/take_poll.html",
        {
            "poll": poll,
            "question": question,
            "previous_question": previous_question,
        },
    )


@login_required
def take_poll(request, poll_id):
    poll = get_object_or_404(Quiz, pk=poll_id)
    if not poll_is_active(poll):
        return HttpResponseNotFound("Срок действия опроса истёк!")
    if PassedPolls.objects.filter(
        quiz=poll,
        passed_user=request.user,
    ).exists():
        return HttpResponseNotFound("Вы уже прошли этот опрос!")

    questions = available_questions(poll)
    if not questions:
        return HttpResponseNotFound("В этом опросе нет вопросов с ответами")

    if request.method == "GET":
        return render_question(request, poll, questions, questions[0])

    question_id = request.POST.get("number_question", "")
    if not question_id.isdigit():
        messages.error(request, "Не удалось определить текущий вопрос.")
        return render_question(request, poll, questions, questions[0])

    question = next(
        (item for item in questions if item.pk == int(question_id)),
        None,
    )
    if question is None:
        return HttpResponseNotFound("Вопрос не принадлежит этому опросу.")

    if request.POST.get("redirect"):
        return render_question(request, poll, questions, question)

    answer_id = request.POST.get("answers", "")
    if not answer_id.isdigit():
        messages.error(request, "Выберите один из вариантов ответа.")
        return render_question(request, poll, questions, question)

    answer = question.answers.filter(pk=int(answer_id)).first()
    if answer is None:
        return HttpResponseNotFound("Ответ не принадлежит этому вопросу.")

    user_answer = (
        UserAnswer.objects
        .filter(quiz=poll, question=question, user=request.user)
        .order_by("pk")
        .first()
    )
    if user_answer is None:
        UserAnswer.objects.create(
            quiz=poll,
            question=question,
            answers=answer,
            user=request.user,
        )
    elif user_answer.answers_id != answer.pk:
        user_answer.answers = answer
        user_answer.save(update_fields=("answers",))

    current_index = questions.index(question)
    if current_index + 1 < len(questions):
        return render_question(
            request,
            poll,
            questions,
            questions[current_index + 1],
        )

    PassedPolls.objects.get_or_create(
        quiz=poll,
        passed_user=request.user,
    )
    messages.info(request, "Вы успешно прошли опрос!")
    return redirect("rating", poll.pk)


@login_required
def rating(request, poll_id):
    quiz = get_object_or_404(Quiz, pk=poll_id)
    if not PassedPolls.objects.filter(
        quiz=quiz,
        passed_user=request.user,
    ).exists():
        return HttpResponseNotFound(
            "Указанный опрос не найден или вы его не прошли!"
        )

    if request.method == "POST":
        rating_value = request.POST.get("rating", "")
        if not rating_value.isdigit() or not 1 <= int(rating_value) <= 5:
            messages.error(request, "Выберите оценку от 1 до 5.")
            return render(request, "questionnaire/rating.html", {"poll": quiz})

        comment = request.POST.get("comment", "").strip()[:750]
        saved_rating = (
            Rating.objects
            .filter(user=request.user, quiz=quiz)
            .order_by("pk")
            .first()
        )
        if saved_rating is None:
            Rating.objects.create(
                answer_number=int(rating_value),
                comment=comment,
                quiz=quiz,
                user=request.user,
            )
        else:
            saved_rating.answer_number = int(rating_value)
            saved_rating.comment = comment
            saved_rating.save(update_fields=("answer_number", "comment"))

        messages.success(request, "Вы успешно оставили отзыв!")
        return redirect("questionnaireIndex")

    return render(request, "questionnaire/rating.html", {"poll": quiz})
