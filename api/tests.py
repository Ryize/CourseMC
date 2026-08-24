import json
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from Course.models import (
    DirectionStudy,
    LearnGroup,
    LessonSolution,
    LessonSolutionFile,
    LessonSolutionSubmission,
    Schedule,
    Student,
    TeacherNotification,
)


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


@override_settings(COURSEMC_BOT_API_TOKEN='test-bot-token')
class BotLessonSolutionApiTests(TestCase):
    def setUp(self):
        self.private_directory = tempfile.TemporaryDirectory()
        self.private_storage_override = override_settings(
            PRIVATE_SOLUTION_MEDIA_ROOT=self.private_directory.name,
        )
        self.private_storage_override.enable()
        self.addCleanup(self.private_storage_override.disable)
        self.addCleanup(self.private_directory.cleanup)

        self.teacher_user = User.objects.create_user(
            'solution-teacher',
            password='teacher-pass',
            is_staff=True,
        )
        self.teacher = Student.objects.create(
            user=self.teacher_user,
            contact='@solution-teacher',
            groups_id=9100,
            is_learned=False,
        )
        self.group = LearnGroup.objects.create(
            pk=9100,
            title='API группа',
            teacher=self.teacher,
            is_studies=True,
        )
        self.student_user = User.objects.create_user(
            'api-student',
            first_name='Иван',
            last_name='Иванов',
            password='student-pass',
        )
        self.student = Student.objects.create(
            user=self.student_user,
            contact='@api-student',
            groups=self.group,
            is_learned=True,
        )
        self.direction = DirectionStudy.objects.create(title='API Backend')
        self.student.direction.add(self.direction)
        self.schedule = Schedule.objects.create(
            direction=self.direction,
            theme='Функции. Практика',
            plan='План',
            lesson_materials='Материалы',
        )
        self.solution = LessonSolution.objects.create(
            schedule=self.schedule,
            student=self.student,
        )
        self.solution_file = LessonSolutionFile.objects.create(
            solution=self.solution,
            file=SimpleUploadedFile('solution.py', b'print("done")'),
            original_name='solution.py',
        )
        self.submission = LessonSolutionSubmission.objects.create(
            solution=self.solution,
            attempt_number=1,
            submitted_at=timezone.now(),
        )
        self.headers = {'HTTP_X_COURSEMC_BOT_TOKEN': 'test-bot-token'}

    def _review(self, payload, *, solution=None, headers=None):
        solution = solution or self.solution
        return self.client.patch(
            reverse('bot_lesson_solution_review', args=(solution.pk,)),
            data=json.dumps(payload),
            content_type='application/json',
            **(self.headers if headers is None else headers),
        )

    def test_queue_requires_bot_token(self):
        response = self.client.get(reverse('bot_lesson_solution_list'))
        self.assertEqual(response.status_code, 403)

    def test_queue_returns_student_lesson_attempt_and_protected_file(self):
        response = self.client.get(
            reverse('bot_lesson_solution_list'),
            {'after': 0, 'teacher_username': self.teacher_user.username},
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['next_cursor'], self.submission.pk)
        result = payload['results'][0]
        self.assertEqual(result['id'], self.solution.pk)
        self.assertEqual(result['submission_id'], self.submission.pk)
        self.assertEqual(result['attempt_number'], 1)
        self.assertEqual(result['student']['username'], 'api-student')
        self.assertEqual(result['student']['display_name'], 'Иван Иванов')
        self.assertEqual(result['group']['title'], self.group.title)
        self.assertEqual(result['lesson']['title'], self.schedule.theme)
        self.assertEqual(result['status'], LessonSolution.Status.PENDING)
        self.assertEqual(result['files'][0]['original_name'], 'solution.py')
        self.assertNotIn(self.solution_file.file.name, response.content.decode())

        cursor_response = self.client.get(
            reverse('bot_lesson_solution_list'),
            {'after': payload['next_cursor']},
            **self.headers,
        )
        self.assertEqual(cursor_response.json()['results'], [])

    def test_resubmission_is_returned_after_previous_cursor(self):
        second_submission = LessonSolutionSubmission.objects.create(
            solution=self.solution,
            attempt_number=2,
            submitted_at=timezone.now(),
        )

        response = self.client.get(
            reverse('bot_lesson_solution_list'),
            {'after': self.submission.pk},
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()['results'][0]
        self.assertEqual(result['submission_id'], second_submission.pk)
        self.assertEqual(result['attempt_number'], 2)

    def test_bot_can_download_file_but_public_request_cannot(self):
        url = reverse(
            'bot_lesson_solution_file',
            args=(self.solution_file.pk,),
        )
        forbidden = self.client.get(url)
        self.assertEqual(forbidden.status_code, 403)

        response = self.client.get(url, **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'print("done")')
        self.assertIn(
            'attachment;',
            response['Content-Disposition'],
        )
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_review_requires_comment_for_revision(self):
        response = self._review({
            'reviewer_username': self.teacher_user.username,
            'status': LessonSolution.Status.NEEDS_REVISION,
            'teacher_comment': '',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('teacher_comment', response.json())

    def test_unrelated_teacher_cannot_review_solution(self):
        other_user = User.objects.create_user(
            'other-solution-teacher',
            password='password',
            is_staff=True,
        )

        response = self._review({
            'reviewer_username': other_user.username,
            'status': LessonSolution.Status.ACCEPTED,
        })

        self.assertEqual(response.status_code, 403)
        self.solution.refresh_from_db()
        self.assertEqual(self.solution.status, LessonSolution.Status.PENDING)

    def test_group_teacher_can_review_and_notification_is_closed(self):
        notification = TeacherNotification.objects.get(
            event_key=f'lesson-submission:{self.submission.pk}',
        )
        self.assertIsNone(notification.read_at)

        response = self._review({
            'reviewer_username': self.teacher_user.username,
            'status': LessonSolution.Status.NEEDS_REVISION,
            'teacher_comment': 'Добавьте обработку пустого списка.',
        })

        self.assertEqual(response.status_code, 200)
        self.solution.refresh_from_db()
        notification.refresh_from_db()
        self.assertEqual(
            self.solution.status,
            LessonSolution.Status.NEEDS_REVISION,
        )
        self.assertEqual(
            self.solution.teacher_comment,
            'Добавьте обработку пустого списка.',
        )
        self.assertEqual(self.solution.reviewed_by, self.teacher_user)
        self.assertIsNotNone(self.solution.reviewed_at)
        self.assertIsNotNone(notification.read_at)
        self.assertEqual(response.json()['status_display'], 'Нужна доработка')

    def test_machine_readable_docs_require_bot_token(self):
        url = reverse('bot_lesson_solution_docs')
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.get(url, **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('queue', response.json()['endpoints'])
