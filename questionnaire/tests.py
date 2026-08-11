from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    AnswerQuestion,
    PassedPolls,
    Question,
    Quiz,
    Rating,
    UserAnswer,
)


class QuestionnaireAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="password")
        self.participant = User.objects.create_user(
            "participant",
            password="password",
        )
        self.other = User.objects.create_user("other", password="password")
        self.quiz = Quiz.objects.create(
            title="Основной опрос",
            description="Описание",
            topic="Python",
            lifetime=timezone.now() + timedelta(days=1),
            user=self.owner,
        )

    def test_private_pages_require_login(self):
        response = self.client.get(reverse("my_poll"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('my_poll')}",
        )

    def test_user_cannot_add_question_to_another_users_quiz(self):
        self.client.force_login(self.other)

        get_response = self.client.get(
            reverse("create_question", args=(self.quiz.pk,))
        )
        post_response = self.client.post(
            reverse("create_question", args=(self.quiz.pk,)),
            {"question": "Чужой вопрос", "quiz": self.quiz.pk},
        )

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        self.assertFalse(Question.objects.filter(question="Чужой вопрос").exists())

    def test_answer_builder_rejects_question_from_another_quiz(self):
        other_quiz = Quiz.objects.create(
            title="Другой опрос",
            description="Описание",
            topic="Django",
            lifetime=timezone.now() + timedelta(days=1),
            user=self.owner,
        )
        other_question = Question.objects.create(
            question="Чужой вопрос",
            quiz=other_quiz,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("create_answer", args=(self.quiz.pk,)),
            {
                "answer": "Неверный вариант",
                "question": other_question.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AnswerQuestion.objects.filter(answer="Неверный вариант").exists()
        )

    def test_internal_pages_use_the_common_coursemc_header(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("create_poll"))

        self.assertContains(response, "CourseMC")
        self.assertContains(response, "Расписания")
        self.assertNotContains(response, "navbar-expand-lg")

    def test_only_owner_can_archive_a_poll(self):
        self.client.force_login(self.other)

        response = self.client.post(reverse("archive_poll", args=(self.quiz.pk,)))

        self.assertEqual(response.status_code, 404)
        self.quiz.refresh_from_db()
        self.assertFalse(self.quiz.is_archived)

    def test_owner_can_edit_existing_question_and_answer(self):
        question = Question.objects.create(
            question="Старый текст вопроса",
            quiz=self.quiz,
        )
        other_question = Question.objects.create(
            question="Другой вопрос",
            quiz=self.quiz,
        )
        answer = AnswerQuestion.objects.create(
            answer="Старый вариант",
            question=question,
            correct=False,
        )
        self.client.force_login(self.owner)

        question_response = self.client.post(
            reverse("edit_question", args=(self.quiz.pk, question.pk)),
            {"question": "Новая формулировка"},
        )
        answer_response = self.client.post(
            reverse("edit_answer", args=(self.quiz.pk, answer.pk)),
            {
                "question": other_question.pk,
                "answer": "Новый правильный вариант",
                "correct": "on",
            },
        )

        self.assertRedirects(question_response, reverse("create_question", args=(self.quiz.pk,)))
        self.assertRedirects(answer_response, reverse("create_answer", args=(self.quiz.pk,)))
        question.refresh_from_db()
        answer.refresh_from_db()
        self.assertEqual(question.question, "Новая формулировка")
        self.assertEqual(answer.answer, "Новый правильный вариант")
        self.assertEqual(answer.question, other_question)
        self.assertTrue(answer.correct)

    def test_non_owner_cannot_edit_existing_question_or_answer(self):
        question = Question.objects.create(
            question="Вопрос владельца",
            quiz=self.quiz,
        )
        answer = AnswerQuestion.objects.create(
            answer="Вариант владельца",
            question=question,
        )
        self.client.force_login(self.other)

        question_response = self.client.get(
            reverse("edit_question", args=(self.quiz.pk, question.pk))
        )
        answer_response = self.client.post(
            reverse("edit_answer", args=(self.quiz.pk, answer.pk)),
            {
                "question": question.pk,
                "answer": "Попытка изменить",
            },
        )

        self.assertEqual(question_response.status_code, 404)
        self.assertEqual(answer_response.status_code, 404)
        answer.refresh_from_db()
        self.assertEqual(answer.answer, "Вариант владельца")


class QuestionnaireArchiveTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="password")
        self.participant = User.objects.create_user(
            "participant",
            password="password",
        )
        self.quiz = Quiz.objects.create(
            title="Опрос в архив",
            description="Описание",
            topic="Python",
            lifetime=timezone.now() + timedelta(days=1),
            user=self.owner,
        )

    def test_archiving_hides_poll_from_active_list_and_closes_it(self):
        self.client.force_login(self.owner)

        response = self.client.post(reverse("archive_poll", args=(self.quiz.pk,)))

        self.assertRedirects(response, reverse("my_poll"))
        self.quiz.refresh_from_db()
        self.assertTrue(self.quiz.is_archived)
        self.assertIsNotNone(self.quiz.archived_at)

        dashboard = self.client.get(reverse("my_poll"))
        self.assertEqual(list(dashboard.context["my_polls"]), [])
        self.assertEqual(list(dashboard.context["archived_polls"]), [self.quiz])

        self.client.force_login(self.participant)
        closed_poll = self.client.get(reverse("take_poll", args=(self.quiz.pk,)))
        self.assertEqual(closed_poll.status_code, 404)

    def test_owner_can_restore_archived_poll(self):
        self.quiz.is_archived = True
        self.quiz.archived_at = timezone.now()
        self.quiz.save(update_fields=("is_archived", "archived_at"))
        self.client.force_login(self.owner)

        response = self.client.post(reverse("restore_poll", args=(self.quiz.pk,)))

        self.assertRedirects(response, reverse("my_poll"))
        self.quiz.refresh_from_db()
        self.assertFalse(self.quiz.is_archived)
        self.assertIsNone(self.quiz.archived_at)


class QuestionnaireResultsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="password")
        self.participant = User.objects.create_user(
            "participant",
            password="password",
        )
        self.other = User.objects.create_user("other", password="password")
        self.quiz = Quiz.objects.create(
            title="Опрос с результатами",
            description="Описание",
            topic="Python",
            lifetime=timezone.now() + timedelta(days=1),
            user=self.owner,
        )
        correct_question = Question.objects.create(
            question="Верный вопрос",
            quiz=self.quiz,
        )
        wrong_question = Question.objects.create(
            question="Вопрос с ошибкой",
            quiz=self.quiz,
        )
        AnswerQuestion.objects.create(
            answer="Правильный ответ",
            question=correct_question,
            correct=True,
        )
        AnswerQuestion.objects.create(
            answer="Правильный вариант",
            question=wrong_question,
            correct=True,
        )
        wrong_answer = AnswerQuestion.objects.create(
            answer="Выбранный неверный вариант",
            question=wrong_question,
            correct=False,
        )
        UserAnswer.objects.create(
            quiz=self.quiz,
            question=correct_question,
            answers=correct_question.answers.get(correct=True),
            user=self.participant,
        )
        UserAnswer.objects.create(
            quiz=self.quiz,
            question=wrong_question,
            answers=wrong_answer,
            user=self.participant,
        )
        PassedPolls.objects.create(quiz=self.quiz, passed_user=self.participant)

    def test_owner_sees_participant_result_and_mistake(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("poll_results", args=(self.quiz.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "participant")
        self.assertContains(response, "50%")
        self.assertContains(response, "Вопрос с ошибкой")
        self.assertContains(response, "Выбранный неверный вариант")
        self.assertContains(response, "Правильный вариант")

    def test_non_owner_cannot_see_results(self):
        self.client.force_login(self.other)

        response = self.client.get(reverse("poll_results", args=(self.quiz.pk,)))

        self.assertEqual(response.status_code, 404)

    def test_dashboard_distinguishes_answer_result_from_poll_rating(self):
        self.client.force_login(self.owner)

        response_without_rating = self.client.get(reverse("my_poll"))

        self.assertContains(response_without_rating, "50%")
        self.assertContains(response_without_rating, "Средняя оценка опроса")
        self.assertContains(response_without_rating, "Оценок пока нет")

        Rating.objects.create(
            quiz=self.quiz,
            user=self.participant,
            answer_number=4,
        )

        response_with_rating = self.client.get(reverse("my_poll"))

        self.assertContains(response_with_rating, "4,0/5")


class QuestionnaireFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="password")
        self.participant = User.objects.create_user(
            "participant",
            password="password",
        )
        self.quiz = Quiz.objects.create(
            title="Опрос с вопросами",
            description="Описание",
            topic="Python",
            lifetime=timezone.now() + timedelta(days=1),
            user=self.owner,
        )
        self.question_one = Question.objects.create(
            question="Первый вопрос",
            quiz=self.quiz,
        )
        filler_quiz = Quiz.objects.create(
            title="Другой опрос",
            description="Описание",
            topic="Django",
            lifetime=timezone.now() + timedelta(days=1),
            user=self.owner,
        )
        Question.objects.create(question="Промежуточный вопрос", quiz=filler_quiz)
        self.question_two = Question.objects.create(
            question="Второй вопрос",
            quiz=self.quiz,
        )
        self.answer_one = AnswerQuestion.objects.create(
            answer="Первый ответ",
            question=self.question_one,
            correct=True,
        )
        self.answer_two = AnswerQuestion.objects.create(
            answer="Второй ответ",
            question=self.question_two,
            correct=True,
        )
        self.client.force_login(self.participant)

    def test_poll_navigation_does_not_depend_on_sequential_ids(self):
        first_response = self.client.get(
            reverse("take_poll", args=(self.quiz.pk,))
        )
        second_response = self.client.post(
            reverse("take_poll", args=(self.quiz.pk,)),
            {
                "number_question": self.question_one.pk,
                "answers": self.answer_one.pk,
            },
        )
        back_response = self.client.post(
            reverse("take_poll", args=(self.quiz.pk,)),
            {
                "number_question": self.question_one.pk,
                "redirect": "1",
            },
        )

        self.assertContains(first_response, "Первый вопрос")
        self.assertContains(second_response, "Второй вопрос")
        self.assertContains(back_response, "Первый вопрос")

    def test_back_button_returns_to_previous_question_without_saving_current(self):
        url = reverse("take_poll", args=(self.quiz.pk,))
        self.client.post(
            url,
            {
                "number_question": self.question_one.pk,
                "answers": self.answer_one.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "number_question": self.question_two.pk,
                "previous_question": self.question_one.pk,
            },
        )

        self.assertContains(response, "Первый вопрос")
        self.assertFalse(
            UserAnswer.objects.filter(
                quiz=self.quiz,
                question=self.question_two,
                user=self.participant,
            ).exists()
        )

    def test_question_text_allows_legacy_breaks_but_escapes_html(self):
        self.question_one.question = "Первая строка<br><script>bad()</script>"
        self.question_one.save(update_fields=("question",))

        response = self.client.get(reverse("take_poll", args=(self.quiz.pk,)))

        self.assertContains(response, "Первая строка<br>", html=False)
        self.assertContains(response, "&lt;script&gt;bad()&lt;/script&gt;", html=False)

    def test_answer_from_another_question_is_rejected(self):
        response = self.client.post(
            reverse("take_poll", args=(self.quiz.pk,)),
            {
                "number_question": self.question_one.pk,
                "answers": self.answer_two.pk,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(UserAnswer.objects.exists())

    def test_repeated_answer_updates_instead_of_creating_duplicate(self):
        alternative = AnswerQuestion.objects.create(
            answer="Другой ответ",
            question=self.question_one,
            correct=False,
        )
        url = reverse("take_poll", args=(self.quiz.pk,))
        self.client.post(
            url,
            {
                "number_question": self.question_one.pk,
                "answers": self.answer_one.pk,
            },
        )
        self.client.post(
            url,
            {
                "number_question": self.question_one.pk,
                "answers": alternative.pk,
            },
        )

        answers = UserAnswer.objects.filter(
            quiz=self.quiz,
            question=self.question_one,
            user=self.participant,
        )
        self.assertEqual(answers.count(), 1)
        self.assertEqual(answers.get().answers, alternative)

    def test_finishing_poll_creates_one_completion_record(self):
        url = reverse("take_poll", args=(self.quiz.pk,))
        self.client.post(
            url,
            {
                "number_question": self.question_one.pk,
                "answers": self.answer_one.pk,
            },
        )
        response = self.client.post(
            url,
            {
                "number_question": self.question_two.pk,
                "answers": self.answer_two.pk,
            },
        )
        repeated_response = self.client.post(
            url,
            {
                "number_question": self.question_two.pk,
                "answers": self.answer_two.pk,
            },
        )

        self.assertRedirects(
            response,
            reverse("rating", args=(self.quiz.pk,)),
        )
        self.assertEqual(repeated_response.status_code, 404)
        self.assertEqual(
            PassedPolls.objects.filter(
                quiz=self.quiz,
                passed_user=self.participant,
            ).count(),
            1,
        )

    def test_rating_is_scoped_to_current_quiz_and_is_updated(self):
        another_quiz = Quiz.objects.create(
            title="Другой опрос",
            description="Описание",
            topic="Django",
            lifetime=timezone.now() + timedelta(days=1),
            user=self.owner,
        )
        PassedPolls.objects.create(
            quiz=another_quiz,
            passed_user=self.participant,
        )

        forbidden_response = self.client.get(
            reverse("rating", args=(self.quiz.pk,))
        )
        PassedPolls.objects.create(
            quiz=self.quiz,
            passed_user=self.participant,
        )
        url = reverse("rating", args=(self.quiz.pk,))
        self.client.post(url, {"rating": "5", "comment": "Отлично"})
        self.client.post(url, {"rating": "3", "comment": "Нормально"})

        self.assertEqual(forbidden_response.status_code, 404)
        ratings = Rating.objects.filter(
            quiz=self.quiz,
            user=self.participant,
        )
        self.assertEqual(ratings.count(), 1)
        self.assertEqual(ratings.get().answer_number, 3)
        self.assertEqual(ratings.get().comment, "Нормально")
