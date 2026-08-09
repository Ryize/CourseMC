import tempfile
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    AdditionalLessons,
    DirectionStudy,
    LearnGroup,
    LessonSolution,
    Schedule,
    Student,
)
from .admin import (
    ActiveGroupListFilter,
    ActiveStudentListFilter,
    AttentionNeededListFilter,
    LessonSolutionAdmin,
    MyGroupsListFilter,
    RecentSolutionListFilter,
    ScheduleAdmin,
    WithoutCommentListFilter,
)
from .views import get_accessible_schedule_ids


class TimetableTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "schedule-user",
            password="password",
        )
        self.direction = DirectionStudy.objects.create(title="Python")
        self.student = Student.objects.create(
            name=self.user.username,
            contact="@student",
            email="student@example.com",
            is_learned=True,
            groups_id=100,
        )
        self.group = LearnGroup.objects.create(
            pk=100,
            title="Учебная группа",
            is_studies=True,
            teacher=self.student,
        )
        self.student.direction.add(self.direction)
        AdditionalLessons.objects.create(group=self.group, amount=10)

        for number in range(25):
            Schedule.objects.create(
                theme=f"Урок {number}",
                plan="План",
                lesson_materials=f"Материалы {number}",
                lesson_type="Новая тема" if number % 2 else "Практика",
                direction=self.direction,
            )

    def test_timetable_requires_learned_student(self):
        anonymous_response = self.client.get(reverse("schedule"))
        another_user = User.objects.create_user(
            "not-a-student",
            password="password",
        )
        self.client.force_login(another_user)
        unrelated_response = self.client.get(reverse("schedule"))

        self.assertEqual(anonymous_response.status_code, 302)
        self.assertRedirects(unrelated_response, reverse("home"))

    def test_timetable_uses_server_side_pagination(self):
        self.client.force_login(self.user)

        first_page = self.client.get(reverse("schedule"))
        second_page = self.client.get(reverse("schedule"), {"page": 2})

        self.assertEqual(len(first_page.context["schedules"]), 20)
        self.assertEqual(len(second_page.context["schedules"]), 5)
        self.assertContains(first_page, "25 урок")
        self.assertContains(second_page, "5 урок")
        self.assertContains(first_page, 'aria-current="page"')
        self.assertContains(first_page, 'aria-label="Страница 2"')
        self.assertContains(second_page, 'aria-label="Страница 1"')

    def test_filter_is_applied_before_pagination(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("schedule"),
            {"lesson_type": "Новая тема"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["schedules"]), 12)
        self.assertTrue(
            all(
                schedule.lesson_type == "Новая тема"
                for schedule in response.context["schedules"]
            )
        )

    def test_ajax_pagination_returns_only_schedule_fragment(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("schedule"),
            {"page": 2},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "Course/includes/schedule_results.html",
        )
        self.assertContains(response, 'id="schedule-results"')
        self.assertContains(response, 'aria-current="page"')
        self.assertNotContains(response, "<html")
        self.assertEqual(len(response.context["schedules"]), 5)

    def test_ajax_filter_returns_only_matching_schedule_fragment(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("schedule"),
            {"lesson_type": "Новая тема"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "Course/includes/schedule_results.html",
        )
        self.assertNotContains(response, "<html")
        self.assertTrue(response.context["schedules"])
        self.assertTrue(
            all(
                schedule.lesson_type == "Новая тема"
                for schedule in response.context["schedules"]
            )
        )


class ScheduleOrderingTests(TimetableTests):
    def test_new_lesson_is_added_to_the_end_of_its_direction(self):
        lesson = Schedule.objects.create(
            theme='Новый урок',
            plan='План',
            lesson_materials='Материалы',
            direction=self.direction,
        )

        self.assertEqual(lesson.position, 26)

    def test_lesson_can_be_inserted_after_another_lesson(self):
        existing_lessons = list(
            Schedule.objects.filter(direction=self.direction).order_by('position', 'pk')
        )
        inserted_lesson = Schedule.objects.create(
            theme='Урок между темами',
            plan='План',
            lesson_materials='Материалы',
            direction=self.direction,
        )
        schedule_admin = ScheduleAdmin(Schedule, admin.site)

        with transaction.atomic():
            schedule_admin._place_after(inserted_lesson, existing_lessons[5])

        ordered_lessons = list(
            Schedule.objects.filter(direction=self.direction).order_by('position', 'pk')
        )
        self.assertEqual(ordered_lessons[6].pk, inserted_lesson.pk)
        self.assertEqual(
            [lesson.position for lesson in ordered_lessons],
            list(range(1, 27)),
        )

    def test_admin_add_form_inserts_lesson_after_selected_one(self):
        admin_user = User.objects.create_superuser(
            'schedule-admin',
            password='password',
        )
        after_lesson = list(
            Schedule.objects.filter(direction=self.direction).order_by('position', 'pk')
        )[3]
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse('admin:Course_schedule_add'),
            {
                'theme': 'Урок из админки',
                'plan': 'План',
                'lesson_materials': 'Материалы',
                'lesson_type': 'Новая тема',
                'direction': self.direction.pk,
                'insert_after': after_lesson.pk,
                '_save': 'Сохранить',
            },
        )

        self.assertEqual(response.status_code, 302)
        inserted_lesson = Schedule.objects.get(theme='Урок из админки')
        ordered_ids = list(
            Schedule.objects.filter(direction=self.direction)
            .order_by('position', 'pk')
            .values_list('pk', flat=True)
        )
        self.assertEqual(
            ordered_ids[ordered_ids.index(after_lesson.pk) + 1],
            inserted_lesson.pk,
        )

    def test_archived_lesson_is_hidden_from_student_program(self):
        archived_lesson = Schedule.objects.filter(direction=self.direction).first()
        archived_lesson.is_archived = True
        archived_lesson.save(update_fields=['is_archived'])
        schedule_admin = ScheduleAdmin(Schedule, admin.site)

        with transaction.atomic():
            schedule_admin._normalize_direction(self.direction.pk)

        available_ids = get_accessible_schedule_ids(self.student)
        active_positions = list(
            Schedule.objects.filter(
                direction=self.direction,
                is_archived=False,
            ).values_list('position', flat=True)
        )
        self.assertNotIn(archived_lesson.pk, available_ids)
        self.assertEqual(active_positions, list(range(1, 25)))


class AdminFilterTests(TimetableTests):
    def test_active_filters_exclude_inactive_students_and_groups(self):
        inactive_group = LearnGroup.objects.create(
            title='Архивная группа',
            is_studies=False,
            teacher=self.student,
        )
        inactive_student = Student.objects.create(
            name='archived-student',
            contact='@archived',
            email='archived@example.com',
            is_learned=False,
            groups=inactive_group,
        )
        request = RequestFactory().get('/admin/Course/lessonsolution/')
        request.user = User.objects.create_superuser(
            'filter-admin',
            password='password',
        )
        model_admin = LessonSolutionAdmin(LessonSolution, admin.site)

        student_filter = ActiveStudentListFilter(
            request,
            {},
            LessonSolution,
            model_admin,
        )
        group_filter = ActiveGroupListFilter(
            request,
            {},
            LessonSolution,
            model_admin,
        )

        self.assertIn(
            (self.student.pk, self.student.name),
            student_filter.lookups(request, model_admin),
        )
        self.assertNotIn(
            (inactive_student.pk, inactive_student.name),
            student_filter.lookups(request, model_admin),
        )
        self.assertIn(
            (self.group.pk, self.group.title),
            group_filter.lookups(request, model_admin),
        )
        self.assertNotIn(
            (inactive_group.pk, inactive_group.title),
            group_filter.lookups(request, model_admin),
        )

    def test_solution_quick_filters_and_my_groups(self):
        schedules = list(Schedule.objects.filter(direction=self.direction)[:3])
        pending_solution = LessonSolution.objects.create(
            student=self.student,
            schedule=schedules[0],
            status=LessonSolution.Status.PENDING,
        )
        revision_solution = LessonSolution.objects.create(
            student=self.student,
            schedule=schedules[1],
            status=LessonSolution.Status.NEEDS_REVISION,
        )
        accepted_solution = LessonSolution.objects.create(
            student=self.student,
            schedule=schedules[2],
            status=LessonSolution.Status.ACCEPTED,
            teacher_comment='Всё хорошо.',
        )
        LessonSolution.objects.filter(pk=accepted_solution.pk).update(
            submitted_at=timezone.now() - timedelta(days=8),
        )
        request = RequestFactory().get('/admin/Course/lessonsolution/')
        request.user = self.user
        model_admin = LessonSolutionAdmin(LessonSolution, admin.site)

        def apply_filter(filter_class, parameter_name, value):
            filter_instance = filter_class(
                request,
                {parameter_name: value},
                LessonSolution,
                model_admin,
            )
            return set(
                filter_instance.queryset(
                    request,
                    LessonSolution.objects.all(),
                ).values_list('pk', flat=True),
            )

        self.assertEqual(
            apply_filter(AttentionNeededListFilter, 'requires_attention', 'yes'),
            {pending_solution.pk, revision_solution.pk},
        )
        self.assertEqual(
            apply_filter(WithoutCommentListFilter, 'without_comment', 'yes'),
            {pending_solution.pk, revision_solution.pk},
        )
        self.assertEqual(
            apply_filter(RecentSolutionListFilter, 'recent_submission', 'week'),
            {pending_solution.pk, revision_solution.pk},
        )
        self.assertEqual(
            apply_filter(MyGroupsListFilter, 'my_groups', 'yes'),
            {pending_solution.pk, revision_solution.pk, accepted_solution.pk},
        )


class LessonSolutionTests(TimetableTests):
    def setUp(self):
        super().setUp()
        self.media_directory = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            PRIVATE_SOLUTION_MEDIA_ROOT=self.media_directory.name,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.schedule = Schedule.objects.order_by('pk').first()
        self.upload_url = reverse(
            'lesson_solution_upload',
            args=(self.schedule.pk,),
        )

    def _upload(self, *files):
        return self.client.post(
            self.upload_url,
            {
                'files': list(files),
                'next': reverse('schedule'),
            },
        )

    def test_student_can_upload_several_files_for_an_available_lesson(self):
        self.client.force_login(self.user)

        response = self._upload(
            SimpleUploadedFile('solution.py', b'print("done")'),
            SimpleUploadedFile('notes.md', b'# Explanation'),
        )

        self.assertRedirects(response, reverse('schedule'))
        solution = LessonSolution.objects.get(
            student=self.student,
            schedule=self.schedule,
        )
        self.assertEqual(solution.status, LessonSolution.Status.PENDING)
        self.assertEqual(solution.files.count(), 2)
        self.assertTrue(
            solution.files.first().file.name.startswith(
                f'solution_uploads/{self.student.pk}/',
            )
        )
        self.assertNotIn('solution.py', solution.files.first().file.name)

    def test_resubmission_replaces_files_and_resets_review_status(self):
        self.client.force_login(self.user)
        self._upload(SimpleUploadedFile('first.py', b'print(1)'))
        solution = LessonSolution.objects.get(
            student=self.student,
            schedule=self.schedule,
        )
        old_file = solution.files.get()
        old_file_name = old_file.file.name
        old_file_storage = old_file.file.storage
        reviewer = User.objects.create_superuser(
            'reviewer',
            password='password',
        )
        solution.status = LessonSolution.Status.NEEDS_REVISION
        solution.teacher_comment = 'Добавь обработку ошибки.'
        solution.reviewed_by = reviewer
        solution.save()

        response = self._upload(SimpleUploadedFile('second.py', b'print(2)'))

        self.assertRedirects(response, reverse('schedule'))
        solution.refresh_from_db()
        self.assertEqual(solution.status, LessonSolution.Status.PENDING)
        self.assertEqual(solution.teacher_comment, '')
        self.assertIsNone(solution.reviewed_by)
        self.assertEqual(solution.files.count(), 1)
        self.assertEqual(solution.files.get().original_name, 'second.py')
        self.assertFalse(old_file_storage.exists(old_file_name))

    def test_upload_rejects_an_unavailable_lesson_and_unsupported_file(self):
        self.client.force_login(self.user)
        other_direction = DirectionStudy.objects.create(title='Java')
        unavailable_schedule = Schedule.objects.create(
            theme='Недоступный урок',
            plan='План',
            lesson_materials='Материалы',
            direction=other_direction,
        )

        unavailable_response = self.client.post(
            reverse('lesson_solution_upload', args=(unavailable_schedule.pk,)),
            {'files': [SimpleUploadedFile('solution.py', b'print(1)')]},
        )
        invalid_file_response = self._upload(
            SimpleUploadedFile('program.exe', b'not executable'),
        )

        self.assertEqual(unavailable_response.status_code, 403)
        self.assertRedirects(invalid_file_response, reverse('schedule'))
        self.assertFalse(
            LessonSolution.objects.filter(
                student=self.student,
                schedule=self.schedule,
            ).exists()
        )

    def test_solution_file_is_available_only_to_owner_or_superuser(self):
        self.client.force_login(self.user)
        self._upload(SimpleUploadedFile('solution.py', b'print("private")'))
        solution_file = LessonSolution.objects.get(
            student=self.student,
            schedule=self.schedule,
        ).files.get()
        download_url = reverse(
            'lesson_solution_file_download',
            args=(solution_file.pk,),
        )

        owner_response = self.client.get(download_url)

        self.assertEqual(owner_response.status_code, 200)
        self.assertIn('attachment;', owner_response['Content-Disposition'])
        self.assertEqual(
            b''.join(owner_response.streaming_content),
            b'print("private")',
        )

        preview_response = self.client.get(f'{download_url}?view=1')

        self.assertEqual(preview_response.status_code, 200)
        self.assertNotIn('attachment;', preview_response.get('Content-Disposition', ''))
        self.assertEqual(
            preview_response['Content-Type'],
            'text/plain; charset=utf-8',
        )
        self.assertEqual(preview_response['X-Content-Type-Options'], 'nosniff')

        other_user = User.objects.create_user('other-student', password='password')
        other_student = Student.objects.create(
            name=other_user.username,
            contact='@other',
            email='other@example.com',
            is_learned=True,
            groups=self.group,
        )
        other_student.direction.add(self.direction)
        self.client.force_login(other_user)
        other_response = self.client.get(download_url)

        self.assertEqual(other_response.status_code, 403)

        superuser = User.objects.create_superuser('admin', password='password')
        self.client.force_login(superuser)
        admin_response = self.client.get(download_url)

        self.assertEqual(admin_response.status_code, 200)

    def test_solution_admin_page_shows_attached_file_links(self):
        self.client.force_login(self.user)
        self._upload(SimpleUploadedFile('solution.py', b'print("shown")'))
        solution = LessonSolution.objects.get(
            student=self.student,
            schedule=self.schedule,
        )
        admin_user = User.objects.create_superuser('files-admin', password='password')
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse('admin:Course_lessonsolution_change', args=(solution.pk,)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'solution.py')
        self.assertContains(response, 'Открыть')
        self.assertContains(response, 'Скачать')

    def test_solution_list_prioritizes_pending_reviews(self):
        self.client.force_login(self.user)
        self._upload(SimpleUploadedFile('pending.py', b'print("pending")'))
        pending_solution = LessonSolution.objects.get(
            student=self.student,
            schedule=self.schedule,
        )
        accepted_schedule = Schedule.objects.exclude(pk=self.schedule.pk).first()
        accepted_solution = LessonSolution.objects.create(
            student=self.student,
            schedule=accepted_schedule,
            status=LessonSolution.Status.ACCEPTED,
        )
        admin_user = User.objects.create_superuser('queue-admin', password='password')
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:Course_lessonsolution_changelist'))
        page = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            page.find(pending_solution.schedule.theme),
            page.find(accepted_solution.schedule.theme),
        )
        self.assertNotContains(response, 'Проверено')
        self.assertNotContains(response, 'Файлов')
        change_url = reverse(
            'admin:Course_lessonsolution_change',
            args=(pending_solution.pk,),
        )
        self.assertContains(response, f'href="{change_url}"', count=5)


class AccountLoginTests(TimetableTests):
    def _login(self, login):
        response = self.client.post(
            reverse('account_login'),
            {'login': login, 'password': 'password'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_user_can_log_in_with_username(self):
        self._login(self.user.username)

    def test_student_can_log_in_with_email_from_profile(self):
        self.assertEqual(self.user.email, '')

        self._login(self.student.email)
