from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView
from django.views.decorators.http import require_POST
from django.utils import timezone

from questionnaire.forms import AnswerForm, QuestionEditForm, QuestionForm, QuizForm
from questionnaire.models import (
    AnswerQuestion,
    PassedPolls,
    Question,
    Quiz,
    Rating,
    UserAnswer,
)
from questionnaire.service import poll_is_active


class QuizListView(LoginRequiredMixin, ListView):
    model = Quiz
    template_name = "questionnaire/my_poll.html"
    context_object_name = "my_polls"
    paginate_by = 16

    def get_poll_queryset(self, is_archived):
        return (
            Quiz.objects
            .filter(user=self.request.user, is_archived=is_archived)
            .order_by("-created_at")
            .prefetch_related(
                "questions__answers",
                "passed_quiz__passed_user",
                "user_quiz__answers",
                "rating",
            )
        )

    def get_queryset(self):
        return self.get_poll_queryset(is_archived=False)

    def enrich_polls(self, polls):
        for poll in polls:
            questions = list(poll.questions.all())
            user_answers = list(poll.user_quiz.all())
            ratings = list(poll.rating.all())
            poll.question_count = len(questions)
            poll.ready_question_count = sum(
                bool(question.answers.all()) for question in questions
            )
            poll.completed_count = len(poll.passed_quiz.all())
            poll.is_active = poll_is_active(poll)
            poll.share_url = self.request.build_absolute_uri(
                reverse("take_poll", args=(poll.pk,))
            )
            poll.average_rating = (
                round(
                    sum(rating.answer_number for rating in ratings) / len(ratings),
                    1,
                )
                if ratings
                else None
            )
            poll.correctness_percent = (
                round(
                    100 * sum(answer.is_correct for answer in user_answers)
                    / len(user_answers)
                )
                if user_answers
                else None
            )
        return polls

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.enrich_polls(context["my_polls"])
        archived_polls = list(self.get_poll_queryset(is_archived=True))
        context["archived_polls"] = self.enrich_polls(archived_polls)
        context["archived_count"] = len(archived_polls)
        return context


def index(request):
    return render(request, "questionnaire/index.html")


def unavailable(request, message, status=404):
    return render(
        request,
        "questionnaire/unavailable.html",
        {"error_message": message},
        status=status,
    )


@login_required
def create_poll(request):
    form = QuizForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        quiz = form.save(commit=False)
        quiz.user = request.user
        quiz.save()
        messages.success(request, "Опрос создан. Добавьте в него первый вопрос.")
        return redirect("create_question", quiz.pk)

    return render(request, "questionnaire/create_poll.html", {"form": form})


@login_required
def create_question(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    form = QuestionForm(quiz, request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Вопрос добавлен. Теперь можно добавить ещё один или варианты ответа.")
        return redirect("create_question", quiz.pk)

    questions = list(quiz.questions.prefetch_related("answers").order_by("pk"))
    for question in questions:
        question.answer_count = len(question.answers.all())
        question.correct_answer_count = sum(
            answer.correct for answer in question.answers.all()
        )
    return render(
        request,
        "questionnaire/create_question.html",
        {
            "form": form,
            "quiz": quiz,
            "questions": questions,
            "question_count": len(questions),
            "ready_question_count": sum(
                bool(question.answers.all()) for question in questions
            ),
        },
    )


@login_required
def create_answer(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    form = AnswerForm(quiz, request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Вариант ответа добавлен.")
        return redirect("create_answer", quiz.pk)

    questions = list(quiz.questions.prefetch_related("answers").order_by("pk"))
    for question in questions:
        question.answer_count = len(question.answers.all())
        question.correct_answer_count = sum(
            answer.correct for answer in question.answers.all()
        )
    return render(
        request,
        "questionnaire/create_answer.html",
        {
            "form": form,
            "quiz": quiz,
            "questions": questions,
            "question_count": len(questions),
            "ready_question_count": sum(
                bool(question.answers.all()) for question in questions
            ),
        },
    )


@login_required
def edit_question(request, quiz_id, question_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    question = get_object_or_404(Question, pk=question_id, quiz=quiz)
    form = QuestionEditForm(request.POST or None, instance=question)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Вопрос изменён.")
        return redirect("create_question", quiz.pk)

    return render(
        request,
        "questionnaire/edit_question.html",
        {
            "form": form,
            "quiz": quiz,
            "question": question,
            "has_completed_responses": quiz.passed_quiz.exists(),
        },
    )


@login_required
def edit_answer(request, quiz_id, answer_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    answer = get_object_or_404(AnswerQuestion, pk=answer_id, question__quiz=quiz)
    form = AnswerForm(quiz, request.POST or None, instance=answer)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Вариант ответа изменён.")
        return redirect("create_answer", quiz.pk)

    return render(
        request,
        "questionnaire/edit_answer.html",
        {
            "form": form,
            "quiz": quiz,
            "answer": answer,
            "has_completed_responses": quiz.passed_quiz.exists(),
        },
    )


@login_required
def create_answer_legacy(request):
    quiz = (
        Quiz.objects
        .filter(user=request.user, is_archived=False)
        .order_by("-created_at")
        .first()
    )
    if quiz is None:
        messages.info(request, "Сначала создайте опрос, затем добавьте варианты ответа.")
        return redirect("create_poll")
    return redirect("create_answer", quiz.pk)


@login_required
@require_POST
def archive_poll(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    if quiz.is_archived:
        messages.info(request, "Этот опрос уже находится в архиве.")
    else:
        quiz.is_archived = True
        quiz.archived_at = timezone.now()
        quiz.save(update_fields=("is_archived", "archived_at"))
        messages.success(
            request,
            "Опрос перенесён в архив и больше недоступен для прохождения."
        )
    return redirect("my_poll")


@login_required
@require_POST
def restore_poll(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    if not quiz.is_archived:
        messages.info(request, "Этот опрос уже находится среди активных.")
    else:
        quiz.is_archived = False
        quiz.archived_at = None
        quiz.save(update_fields=("is_archived", "archived_at"))
        messages.success(request, "Опрос возвращён из архива.")
    return redirect("my_poll")


@login_required
def poll_results(request, quiz_id):
    """Показывает автору опроса результаты всех завершённых прохождений."""
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    questions = list(
        quiz.questions
        .prefetch_related("answers")
        .filter(answers__isnull=False)
        .distinct()
        .order_by("pk")
    )
    completions = list(
        PassedPolls.objects
        .filter(quiz=quiz)
        .select_related("passed_user")
        .order_by("-created_at", "-pk")
    )
    user_ids = [completion.passed_user_id for completion in completions]
    answers_by_user = {user_id: [] for user_id in user_ids}

    for user_answer in (
        UserAnswer.objects
        .filter(quiz=quiz, user_id__in=user_ids)
        .select_related("question", "answers")
        .order_by("question__pk", "pk")
    ):
        answers_by_user[user_answer.user_id].append(user_answer)

    question_numbers = {
        question.pk: index
        for index, question in enumerate(questions, start=1)
    }
    correct_answers = {
        question.pk: ", ".join(
            answer.answer
            for answer in question.answers.all()
            if answer.correct
        )
        for question in questions
    }
    results = []
    for completion in completions:
        answers = answers_by_user.get(completion.passed_user_id, [])
        correct_count = sum(answer.is_correct for answer in answers)
        mistakes = []
        for answer in answers:
            if answer.is_correct:
                continue
            mistakes.append({
                "number": question_numbers.get(answer.question_id, "—"),
                "question": answer.question.question,
                "selected_answer": answer.answers.answer,
                "correct_answer": correct_answers.get(answer.question_id, "—"),
            })
        result = completion
        result.answer_count = len(answers)
        result.correct_count = correct_count
        result.mistakes = mistakes
        result.correctness_percent = (
            round(correct_count / len(answers) * 100)
            if answers
            else 0
        )
        results.append(result)

    all_answers = [
        answer
        for answers in answers_by_user.values()
        for answer in answers
    ]
    correct_answers_count = sum(answer.is_correct for answer in all_answers)
    correctness_percent = (
        round(correct_answers_count / len(all_answers) * 100)
        if all_answers
        else None
    )

    return render(
        request,
        "questionnaire/poll_results.html",
        {
            "poll": quiz,
            "results": results,
            "question_count": len(questions),
            "completion_count": len(completions),
            "correctness_percent": correctness_percent,
        },
    )


@login_required
def go_poll(request):
    if request.method == "GET":
        return render(request, "questionnaire/go_poll.html")

    poll_id = request.POST.get("poll_id", "")
    if not poll_id.isdigit():
        messages.error(request, "Введите номер опроса целиком.")
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
    question_index = questions.index(question)
    previous_question = questions[question_index - 1] if question_index else None
    selected_answer_id = (
        UserAnswer.objects
        .filter(quiz=poll, question=question, user=request.user)
        .values_list("answers_id", flat=True)
        .first()
    )
    return render(
        request,
        "questionnaire/take_poll.html",
        {
            "poll": poll,
            "question": question,
            "previous_question": previous_question,
            "question_position": question_index + 1,
            "question_total": len(questions),
            "selected_answer_id": selected_answer_id,
        },
    )


@login_required
def take_poll(request, poll_id):
    poll = get_object_or_404(Quiz, pk=poll_id)
    if poll.is_archived:
        return unavailable(request, "Автор перенёс этот опрос в архив.")
    if not poll_is_active(poll):
        return unavailable(request, "Срок действия этого опроса уже истёк.")
    if PassedPolls.objects.filter(quiz=poll, passed_user=request.user).exists():
        return unavailable(request, "Вы уже прошли этот опрос.")

    questions = available_questions(poll)
    if not questions:
        return unavailable(request, "В этом опросе пока нет вопросов с вариантами ответа.")

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
        return unavailable(request, "Этот вопрос не относится к выбранному опросу.")

    previous_question_id = request.POST.get("previous_question", "")
    if previous_question_id.isdigit():
        previous_question = next(
            (item for item in questions if item.pk == int(previous_question_id)),
            None,
        )
        if previous_question is None:
            return unavailable(request, "Этот вопрос не относится к выбранному опросу.")
        return render_question(request, poll, questions, previous_question)

    answer_id = request.POST.get("answers", "")
    if not answer_id.isdigit():
        messages.error(request, "Выберите один из вариантов ответа.")
        return render_question(request, poll, questions, question)

    answer = question.answers.filter(pk=int(answer_id)).first()
    if answer is None:
        return unavailable(request, "Этот вариант ответа не относится к текущему вопросу.")

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
            is_correct=answer.correct,
        )
    elif user_answer.answers_id != answer.pk:
        user_answer.answers = answer
        user_answer.is_correct = answer.correct
        user_answer.save(update_fields=("answers", "is_correct"))

    current_index = questions.index(question)
    if current_index + 1 < len(questions):
        return render_question(
            request,
            poll,
            questions,
            questions[current_index + 1],
        )

    PassedPolls.objects.get_or_create(quiz=poll, passed_user=request.user)
    messages.success(request, "Опрос пройден. Оцените его, пожалуйста.")
    return redirect("rating", poll.pk)


@login_required
def rating(request, poll_id):
    quiz = get_object_or_404(Quiz, pk=poll_id)
    if not PassedPolls.objects.filter(quiz=quiz, passed_user=request.user).exists():
        return unavailable(request, "Оценить можно только уже пройденный опрос.")

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

        messages.success(request, "Спасибо за отзыв!")
        return redirect("questionnaireIndex")

    return render(request, "questionnaire/rating.html", {"poll": quiz})
