from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from Course.models import DirectionStudy, LearnGroup, Student

from .admin import (
    ProjectForReviewAdmin,
    ProjectStudentListFilter,
    ProjectStudentScopeListFilter,
)
from .models import ProjectCategories, ProjectForReview


class CodeReviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "review-user",
            email="student@example.com",
            password="password",
        )
        self.other_user = User.objects.create_user(
            "other-review-user",
            email="other@example.com",
            password="password",
        )
        self.staff = User.objects.create_user(
            "review-admin",
            password="password",
            is_staff=True,
        )
        self.direction = DirectionStudy.objects.create(title="Python")
        self.student = Student.objects.create(
            user=self.user,
            contact="@student",
            is_learned=True,
            groups_id=200,
        )
        self.group = LearnGroup.objects.create(
            pk=200,
            title="Учебная группа",
            is_studies=True,
            teacher=self.student,
        )
        self.student.direction.add(self.direction)
        self.other_student = Student.objects.create(
            user=self.other_user,
            contact="@other",
            is_learned=True,
            groups=self.group,
        )
        self.other_student.direction.add(self.direction)
        self.category = ProjectCategories.objects.create(
            title="Учебный проект",
            min_lines=10,
            min_cognetive=1,
            max_cognetive=100,
        )

    def create_review(self, student=None, number=1):
        return ProjectForReview.objects.create(
            category=self.category,
            github=f"https://github.com/example/project-{number}",
            comment="Комментарий",
            user=student or self.student,
            lines=50,
            cognetive=10,
        )

    def test_pages_require_login_and_student_role(self):
        anonymous_response = self.client.get(reverse("review_list"))
        unrelated_user = User.objects.create_user(
            "not-a-student",
            password="password",
        )
        self.client.force_login(unrelated_user)
        forbidden_response = self.client.get(reverse("review_list"))

        self.assertEqual(anonymous_response.status_code, 302)
        self.assertEqual(forbidden_response.status_code, 403)

    def test_student_sees_only_own_reviews_but_staff_sees_all(self):
        own_review = self.create_review()
        other_review = self.create_review(self.other_student, 2)

        self.client.force_login(self.user)
        student_response = self.client.get(reverse("review_list"))
        self.client.force_login(self.staff)
        staff_response = self.client.get(reverse("review_list"))

        student_review_ids = {
            review.pk for review in student_response.context["reviews"]
        }
        staff_review_ids = {
            review.pk for review in staff_response.context["reviews"]
        }
        self.assertEqual(student_review_ids, {own_review.pk})
        self.assertEqual(staff_review_ids, {own_review.pk, other_review.pk})

    def test_student_cannot_open_another_students_review(self):
        other_review = self.create_review(self.other_student)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("review_my", args=(other_review.pk,))
        )

        self.assertEqual(response.status_code, 403)

    def test_review_list_uses_server_side_pagination(self):
        for number in range(21):
            self.create_review(number=number)
        self.client.force_login(self.user)

        first_page = self.client.get(reverse("review_list"))
        second_page = self.client.get(reverse("review_list"), {"page": 2})

        self.assertEqual(len(first_page.context["reviews"]), 20)
        self.assertEqual(len(second_page.context["reviews"]), 1)
        self.assertContains(first_page, 'aria-current="page"')
        self.assertContains(first_page, 'aria-label="Страница 2"')

    def test_review_pages_have_a_mobile_viewport(self):
        review = self.create_review()
        self.client.force_login(self.user)

        for url in (
            reverse("review_list"),
            reverse("review_send"),
            reverse("review_my", args=(review.pk,)),
        ):
            response = self.client.get(url)

            self.assertContains(
                response,
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
                html=False,
            )

    @patch(
        "codereview.views.get_project_info",
        return_value={"all_cognetive": 10, "all_size": 50},
    )
    def test_valid_submission_is_created_once(self, analyse_repository):
        self.client.force_login(self.user)
        url = reverse("review_send")
        data = {
            "category": self.category.pk,
            "github": "https://github.com/example/project",
            "comment": "Проверьте проект",
        }

        first_response = self.client.post(url, data)
        second_response = self.client.post(url, data)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(ProjectForReview.objects.count(), 1)
        analyse_repository.assert_called_once_with("example/project")

    def test_invalid_repository_keeps_form_errors(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("review_send"),
            {
                "category": self.category.pk,
                "github": "https://example.com/not-github",
                "comment": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Укажите ссылку на репозиторий GitHub")
        self.assertFalse(ProjectForReview.objects.exists())

    def test_admin_filters_current_students_and_keeps_archive_available(self):
        current_project = self.create_review(self.student)
        archive_group = LearnGroup.objects.create(
            title='Архивная группа',
            is_studies=False,
            teacher=self.student,
        )
        archive_user = User.objects.create_user(
            'archive-review-student',
            email='archive-review@example.com',
            password='password',
        )
        archive_student = Student.objects.create(
            user=archive_user,
            contact='@archive',
            is_learned=False,
            groups=archive_group,
        )
        archive_project = self.create_review(archive_student, 2)
        model_admin = ProjectForReviewAdmin(ProjectForReview, admin.site)

        current_request = RequestFactory().get('/admin/codereview/projectforreview/')
        current_scope_filter = ProjectStudentScopeListFilter(
            current_request,
            {},
            ProjectForReview,
            model_admin,
        )
        current_student_filter = ProjectStudentListFilter(
            current_request,
            {},
            ProjectForReview,
            model_admin,
        )
        current_ids = set(
            current_scope_filter.queryset(
                current_request,
                ProjectForReview.objects.all(),
            ).values_list('pk', flat=True),
        )

        archive_request = RequestFactory().get(
            '/admin/codereview/projectforreview/',
            {'student_scope': 'archive'},
        )
        archive_scope_filter = ProjectStudentScopeListFilter(
            archive_request,
            {'student_scope': 'archive'},
            ProjectForReview,
            model_admin,
        )
        archive_student_filter = ProjectStudentListFilter(
            archive_request,
            {},
            ProjectForReview,
            model_admin,
        )
        archive_ids = set(
            archive_scope_filter.queryset(
                archive_request,
                ProjectForReview.objects.all(),
            ).values_list('pk', flat=True),
        )

        self.assertIn(current_project.pk, current_ids)
        self.assertNotIn(archive_project.pk, current_ids)
        self.assertIn(archive_project.pk, archive_ids)
        self.assertNotIn(current_project.pk, archive_ids)
        self.assertNotIn(
            (archive_student.pk, archive_student.user.username),
            current_student_filter.lookups(current_request, model_admin),
        )
        self.assertIn(
            (archive_student.pk, archive_student.user.username),
            archive_student_filter.lookups(archive_request, model_admin),
        )
