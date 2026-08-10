from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from interview.answer import get_questions, mark_questions_as_shown
from interview.models import (
    InterviewQuestion,
    InterviewQuestionCategory,
    InterviewQuestionProgress,
)


class InterviewViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='interview-test-user',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.python = InterviewQuestionCategory.objects.create(title='Python')
        self.hr = InterviewQuestionCategory.objects.create(title='HR')

        for index in range(5):
            InterviewQuestion.objects.create(
                title=f'Python question {index}',
                theme=self.python,
                percent=1,
                complexity=1,
            )
            InterviewQuestion.objects.create(
                title=f'HR question {index}',
                theme=self.hr,
                percent=1,
                complexity=1,
            )

    def get_as_student(self, params):
        student = SimpleNamespace(is_learned=True, save=lambda: None)
        with patch(
            'interview.views.Student.objects.for_user',
            return_value=student,
        ):
            return self.client.get('/interview/', params)

    def test_random_mode_ignores_hidden_python_complexity(self):
        response = self.get_as_student({
            'amount': 10,
            'technologies': 'random',
            'start': 8,
            'end': 9,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['question']), 10)
        self.assertTrue(response.context['random_mode'])
        self.assertContains(
            response,
            'name="technologies" value="random"',
            html=False,
        )
        self.assertContains(
            response,
            'class="interview-question-toggle"',
            html=False,
        )
        self.assertEqual(
            InterviewQuestionProgress.objects.filter(user=self.user).count(),
            10,
        )
        self.assertFalse(
            InterviewQuestionProgress.objects.filter(
                user=self.user,
                status=InterviewQuestionProgress.Status.UNRATED,
            ).exists()
        )

    def test_invalid_amount_returns_form_instead_of_server_error(self):
        response = self.get_as_student({'amount': 'not-a-number'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interview/index.html')

    def test_invalid_python_range_uses_safe_defaults(self):
        response = self.get_as_student({
            'amount': 10,
            'technologies': 'Python',
            'start': 'not-a-number',
            'end': 9,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['start'], 1)
        self.assertEqual(response.context['end'], 3)
        self.assertEqual(len(response.context['question']), 5)

    def test_named_category_has_priority_over_random_choice(self):
        response = self.get_as_student({
            'amount': 10,
            'technologies': ['random', 'Python'],
            'start': 1,
            'end': 3,
        })

        self.assertFalse(response.context['random_mode'])
        self.assertEqual(response.context['technologies'], ['Python'])
        self.assertTrue(all(
            question.theme.title == 'Python'
            for question in response.context['question']
        ))

    def test_answered_question_is_excluded_until_cooldown_ends(self):
        question = InterviewQuestion.objects.filter(theme=self.python).first()
        now = timezone.now()
        InterviewQuestionProgress.objects.create(
            user=self.user,
            question=question,
            status=InterviewQuestionProgress.Status.ANSWERED,
            last_shown_at=now,
            next_available_at=now + timedelta(days=14),
        )

        questions = get_questions(
            InterviewQuestion.objects.filter(theme=self.python).select_related('theme'),
            ['Python'],
            5,
            user=self.user,
            now=now,
        )

        self.assertNotIn(question, questions)

    def test_repeat_questions_are_prioritized_but_limited(self):
        for index in range(5, 10):
            InterviewQuestion.objects.create(
                title=f'Python question {index}',
                theme=self.python,
                percent=1,
                complexity=1,
            )
        questions = list(
            InterviewQuestion.objects.filter(theme=self.python).select_related('theme')
        )
        now = timezone.now()
        repeat_questions = questions[:4]
        for question in repeat_questions:
            InterviewQuestionProgress.objects.create(
                user=self.user,
                question=question,
                status=InterviewQuestionProgress.Status.REPEAT,
                last_shown_at=now,
                next_available_at=now,
            )

        selected_questions = get_questions(
            InterviewQuestion.objects.filter(theme=self.python).select_related('theme'),
            ['Python'],
            5,
            user=self.user,
            now=now,
        )

        selected_repeat_count = sum(
            question in repeat_questions for question in selected_questions
        )
        self.assertEqual(selected_repeat_count, 2)
        self.assertEqual(len(selected_questions), 5)

    def test_progress_endpoint_only_updates_issued_question(self):
        question = InterviewQuestion.objects.filter(theme=self.python).first()
        mark_questions_as_shown(self.user, [question])

        with patch(
            'interview.views.Student.objects.for_user',
            return_value=SimpleNamespace(is_learned=True),
        ):
            answered_response = self.client.post(
                reverse('interview_question_progress', args=(question.pk,)),
                {'action': 'answered'},
            )
            progress = InterviewQuestionProgress.objects.get(
                user=self.user,
                question=question,
            )
            self.assertEqual(
                progress.status,
                InterviewQuestionProgress.Status.ANSWERED,
            )
            self.assertGreater(
                progress.next_available_at,
                timezone.now() + timedelta(days=13),
            )
            repeat_response = self.client.post(
                reverse('interview_question_progress', args=(question.pk,)),
                {'action': 'repeat'},
            )
            missing_response = self.client.post(
                reverse('interview_question_progress', args=(999999,)),
                {'action': 'answered'},
            )

        progress = InterviewQuestionProgress.objects.get(
            user=self.user,
            question=question,
        )
        self.assertEqual(answered_response.status_code, 200)
        self.assertEqual(repeat_response.status_code, 200)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(progress.status, InterviewQuestionProgress.Status.REPEAT)
        self.assertLessEqual(progress.next_available_at, timezone.now())
