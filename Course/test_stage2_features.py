import tempfile
from decimal import Decimal
from io import BytesIO

from PIL import Image
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from codereview.models import ProjectCategories, ProjectForReview

from .admin import ScheduleAdmin
from .curriculum import create_curriculum_draft, publish_curriculum_version
from .models import (
    CurriculumLesson,
    CurriculumVersion,
    DirectionStudy,
    LearnGroup,
    LessonSolution,
    LessonSolutionSubmission,
    Schedule,
    Student,
    StudentQuestion,
    TeacherNotification,
)


class LearningTeamMixin:
    def create_teacher_and_group(self, suffix='main'):
        user = User.objects.create_user(
            f'teacher-{suffix}',
            password='password',
            is_staff=True,
        )
        group_id = 8000 + User.objects.count()
        teacher = Student.objects.create(
            user=user,
            contact='@teacher',
            groups_id=group_id,
            is_learned=False,
        )
        group = LearnGroup.objects.create(
            pk=group_id,
            title=f'Группа {suffix}',
            teacher=teacher,
        )
        return user, teacher, group

    def create_student(self, group, suffix='student', active=True):
        user = User.objects.create_user(suffix, password='password')
        return Student.objects.create(
            user=user,
            contact=f'@{suffix}',
            groups=group,
            is_learned=active,
        )


class AutomaticGroupActivityTests(LearningTeamMixin, TestCase):
    def test_group_follows_active_students_and_group_moves(self):
        _, _, first_group = self.create_teacher_and_group('first')
        _, _, second_group = self.create_teacher_and_group('second')
        self.assertFalse(first_group.is_studies)

        student = self.create_student(first_group, 'active-student')
        first_group.refresh_from_db()
        self.assertTrue(first_group.is_studies)

        student.groups = second_group
        student.save(update_fields=('groups',))
        first_group.refresh_from_db()
        second_group.refresh_from_db()
        self.assertFalse(first_group.is_studies)
        self.assertTrue(second_group.is_studies)

        student.is_learned = False
        student.save(update_fields=('is_learned',))
        second_group.refresh_from_db()
        self.assertFalse(second_group.is_studies)


class TeacherNotificationTests(LearningTeamMixin, TestCase):
    def setUp(self):
        self.teacher_user, _, self.group = self.create_teacher_and_group()
        self.student = self.create_student(self.group)
        self.direction = DirectionStudy.objects.create(title='Уведомления')
        self.lesson = Schedule.objects.create(
            direction=self.direction,
            theme='Словари',
            plan='План',
            lesson_materials='Задание',
        )

    def test_teacher_receives_all_three_operational_notifications(self):
        question = StudentQuestion.objects.create(
            group=self.group,
            question='Можно уточнить условие?',
        )
        solution = LessonSolution.objects.create(
            schedule=self.lesson,
            student=self.student,
        )
        LessonSolutionSubmission.objects.create(
            solution=solution,
            attempt_number=1,
            submitted_at=question.created_at,
        )
        category = ProjectCategories.objects.create(
            title='Тестовый проект',
            min_lines=1,
            min_cognetive=1,
            max_cognetive=10,
        )
        ProjectForReview.objects.create(
            category=category,
            user=self.student,
            github='https://github.com/example/project',
        )

        notifications = TeacherNotification.objects.filter(
            recipient=self.teacher_user,
        )
        self.assertEqual(notifications.count(), 3)
        self.assertSetEqual(
            set(notifications.values_list('kind', flat=True)),
            {
                TeacherNotification.Kind.STUDENT_QUESTION,
                TeacherNotification.Kind.LESSON_SOLUTION,
                TeacherNotification.Kind.CODE_REVIEW,
            },
        )

        notification = notifications.first()
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse(
            'admin:Course_teachernotification_open',
            args=(notification.pk,),
        ))
        self.assertRedirects(
            response,
            notification.target_url,
            fetch_redirect_response=False,
        )
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)


class CurriculumVersionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            'curriculum-admin',
            email='admin@example.com',
            password='password',
        )
        self.direction = DirectionStudy.objects.create(title='Версии Python')
        self.first = Schedule.objects.create(
            direction=self.direction,
            theme='Первый урок',
            plan='Первый план',
            lesson_materials='Первое задание',
        )
        self.second = Schedule.objects.create(
            direction=self.direction,
            theme='Второй урок',
            plan='Второй план',
            lesson_materials='Второе задание',
        )

    def test_draft_does_not_change_live_program_until_publish(self):
        version = create_curriculum_draft(self.direction, self.user)
        draft_first = version.lessons.get(source_schedule=self.first)
        draft_first.theme = 'Обновлённый первый урок'
        draft_first.save(update_fields=('theme',))
        version.lessons.get(source_schedule=self.second).delete()
        CurriculumLesson.objects.create(
            version=version,
            position=Decimal('1.500'),
            theme='Новый урок между уроками',
            plan='Новый план',
            lesson_materials='Новое задание',
        )

        self.first.refresh_from_db()
        self.assertEqual(self.first.theme, 'Первый урок')
        self.assertFalse(self.second.is_archived)

        publish_curriculum_version(version, self.user)

        version.refresh_from_db()
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        live_lessons = list(
            Schedule.objects
            .filter(direction=self.direction, is_archived=False)
            .order_by('position')
        )
        self.assertEqual(version.status, CurriculumVersion.Status.PUBLISHED)
        self.assertEqual(self.first.theme, 'Обновлённый первый урок')
        self.assertTrue(self.second.is_archived)
        self.assertEqual(
            [lesson.theme for lesson in live_lessons],
            ['Обновлённый первый урок', 'Новый урок между уроками'],
        )
        self.assertEqual([lesson.position for lesson in live_lessons], [1, 2])

    def test_publish_refuses_to_overwrite_program_changed_after_draft(self):
        version = create_curriculum_draft(self.direction, self.user)
        self.first.theme = 'Срочное изменение в опубликованной версии'
        self.first.save(update_fields=('theme',))

        with self.assertRaises(ValidationError):
            publish_curriculum_version(version, self.user)

        version.refresh_from_db()
        self.assertEqual(version.status, CurriculumVersion.Status.DRAFT)

    def test_published_program_is_read_only_for_regular_staff(self):
        staff_user = User.objects.create_user(
            'curriculum-editor',
            password='password',
            is_staff=True,
        )
        request = RequestFactory().get('/coursemc_control/Course/schedule/')
        request.user = staff_user
        schedule_admin = ScheduleAdmin(Schedule, admin.site)

        self.assertFalse(schedule_admin.has_add_permission(request))
        self.assertFalse(
            schedule_admin.has_change_permission(request, self.first),
        )
        self.assertFalse(
            schedule_admin.has_delete_permission(request, self.first),
        )


class RichTextEditorUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('editor-user', password='password')

    @staticmethod
    def image_file():
        stream = BytesIO()
        Image.new('RGB', (20, 20), '#6757e8').save(stream, format='PNG')
        return SimpleUploadedFile('lesson.png', stream.getvalue(), 'image/png')

    def test_upload_requires_login_and_rejects_non_images(self):
        url = reverse('rich_text_image_upload')
        anonymous = self.client.post(url, {'files': self.image_file()})
        self.assertEqual(anonymous.status_code, 302)

        self.client.force_login(self.user)
        invalid = self.client.post(url, {
            'files': SimpleUploadedFile('fake.png', b'not-an-image', 'image/png'),
        })
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(invalid.json()['success'])

    def test_valid_image_is_saved_with_random_safe_name(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.client.force_login(self.user)
                response = self.client.post(
                    reverse('rich_text_image_upload'),
                    {'files': self.image_file()},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertNotIn('lesson.png', payload['files'][0])
