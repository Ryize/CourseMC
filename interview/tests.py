from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from interview.models import InterviewQuestion, InterviewQuestionCategory


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
        with patch('interview.views.Student.objects.filter') as student_filter:
            student_filter.return_value.first.return_value = student
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
