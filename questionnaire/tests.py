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
