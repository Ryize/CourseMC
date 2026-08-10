from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from Course.models import LearnGroup, Student


@override_settings(COURSEMC_BOT_API_TOKEN='test-bot-token')
class BotStudentApiTests(TestCase):
    def setUp(self):
        teacher_user = User.objects.create_user(
            'teacher', email='teacher@example.com', password='teacher-pass',
        )
        teacher = Student.objects.create(
            user=teacher_user,
            contact='@teacher',
            is_learned=False,
        )
        self.group = LearnGroup.objects.create(
            title='Тестовая группа',
            teacher=teacher,
            is_studies=True,
        )
        teacher.groups = self.group
        teacher.save(update_fields=('groups',))
        self.user = User.objects.create_user(
            'student',
            email='student@example.com',
            password='safe-password',
        )
        self.student = Student.objects.create(
            user=self.user,
            contact='@student',
            groups=self.group,
            is_learned=True,
        )
        self.headers = {'HTTP_X_COURSEMC_BOT_TOKEN': 'test-bot-token'}

    def test_authentication_requires_bot_token(self):
        response = self.client.post(
            reverse('bot_student_authenticate'),
            {'login': 'student', 'password': 'safe-password'},
        )
        self.assertEqual(response.status_code, 403)

    def test_authenticates_by_username_without_exposing_password(self):
        response = self.client.post(
            reverse('bot_student_authenticate'),
            {'login': 'student', 'password': 'safe-password'},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['username'], 'student')
        self.assertNotIn('password', response.json())

    def test_rejects_legacy_plaintext_password(self):
        response = self.client.post(
            reverse('bot_student_authenticate'),
            {'login': 'student', 'password': 'obsolete-plain-password'},
            **self.headers,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {'authenticated': False})

    def test_returns_only_active_students_from_requested_group(self):
        inactive_user = User.objects.create_user(
            'inactive', email='inactive@example.com', password='password',
        )
        Student.objects.create(
            user=inactive_user,
            contact='@inactive',
            groups=self.group,
            is_learned=False,
        )

        response = self.client.get(
            reverse('bot_group_students', args=(self.group.pk,)),
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'usernames': ['student']})

    def test_public_student_list_is_closed(self):
        response = self.client.get('/api/v1/student/')
        self.assertEqual(response.status_code, 403)
