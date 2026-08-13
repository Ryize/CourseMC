import json
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from Course.models import DirectionStudy, LearnGroup, Student

from .admin import (
    CodeReviewAdmin,
    ProjectForReviewAdmin,
    ProjectStudentListFilter,
    ProjectStudentScopeListFilter,
)
from .ai_review import SourceBundle, generate_ai_review_draft
from .git_urls import tree_to_urls
from .models import CodeReview, ProjectCategories, ProjectForReview


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
            is_superuser=True,
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

    @patch(
        "codereview.views.generate_ai_review_draft",
    )
    @patch(
        "codereview.views.get_project_info",
        return_value={"all_cognetive": 10, "all_size": 50},
    )
    def test_valid_submission_starts_ai_draft(
        self,
        analyse_repository,
        generate_draft,
    ):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("review_send"),
            {
                "category": self.category.pk,
                "github": "https://github.com/example/project",
                "comment": "Проверьте проект",
            },
        )

        self.assertEqual(response.status_code, 302)
        generate_draft.assert_called_once_with(ProjectForReview.objects.get())

    def test_student_cannot_see_unpublished_ai_draft(self):
        project = self.create_review()
        CodeReview.objects.create(
            project=project,
            problems="<p>Черновик ИИ с проблемой</p>",
            amount_problems=1,
            is_ai_generated=True,
            ai_generation_status="ready",
            is_published=False,
            status=False,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("review_my", args=(project.pk,)))

        self.assertContains(response, "Ревью пока не готово")
        self.assertNotContains(response, "Черновик ИИ с проблемой")

        list_response = self.client.get(reverse("review_list"))
        self.assertNotContains(list_response, "❌ Не пройдено")
        self.assertNotContains(
            list_response,
            reverse("review_my", args=(project.pk,)),
        )

    def test_admin_marks_revealed_review_as_approved(self):
        project = self.create_review()
        review = CodeReview.objects.create(project=project, is_published=False)
        review.is_published = True
        request = RequestFactory().post("/admin/codereview/codereview/")
        request.user = self.staff
        model_admin = CodeReviewAdmin(CodeReview, admin.site)

        model_admin.save_model(request, review, form=None, change=True)

        review.refresh_from_db()
        self.assertEqual(review.approved_by, self.staff)
        self.assertIsNotNone(review.approved_at)

    def test_admin_project_list_links_to_ai_draft(self):
        project = self.create_review()
        draft = CodeReview.objects.create(
            project=project,
            is_ai_generated=True,
            ai_generation_status='ready',
        )
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('admin:codereview_projectforreview_changelist')
        )

        self.assertContains(response, 'Черновик готов')
        self.assertContains(
            response,
            reverse('admin:codereview_codereview_change', args=(draft.pk,)),
        )

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
            {'student_scope': ['archive']},
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


class GitUrlTests(TestCase):
    def test_root_non_python_files_are_not_sent_to_complexity_analyser(self):
        tree = {
            'demo': {
                'files': ['.gitignore', 'README.md', 'manage.py'],
                'dirs': {},
            },
        }

        urls = tree_to_urls(tree, 'owner/demo', 'main')

        self.assertEqual(
            urls,
            ['https://raw.githubusercontent.com/owner/demo/main/manage.py'],
        )


class AIReviewDraftTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("review-owner", password="password")
        self.direction = DirectionStudy.objects.create(title="Python")
        self.student = Student.objects.create(
            user=self.owner,
            contact="@owner",
            is_learned=True,
            groups_id=333,
        )
        group = LearnGroup.objects.create(
            pk=333,
            title="Группа для ИИ-ревью",
            is_studies=True,
            teacher=self.student,
        )
        self.student.groups = group
        self.student.save(update_fields=("groups",))
        self.student.direction.add(self.direction)
        self.category = ProjectCategories.objects.create(
            title="Проект для ИИ-ревью",
            min_lines=10,
            min_cognetive=1,
            max_cognetive=100,
        )
        self.project = ProjectForReview.objects.create(
            category=self.category,
            user=self.student,
            github="https://github.com/example/project",
            lines=50,
            cognetive=10,
        )

    @override_settings(PROXYAPI_API_KEY="test-key", PROXYAPI_REVIEW_MODEL="gpt-4o-mini")
    @patch(
        "codereview.ai_review.collect_repository_source",
        return_value=SourceBundle(
            content="\n### Файл: app.py\n```python\nprint('hello')\n```",
            summary="Передано 1 из 1 Python-файлов, 14 символов",
        ),
    )
    @patch("codereview.ai_review.requests.post")
    def test_generation_creates_hidden_safe_draft(self, post, collect_source):
        response = post.return_value
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "issues": [
                                    {
                                        "file": "app.py",
                                        "problem": "В коде есть <script>опасная строка</script>",
                                    }
                                ],
                                "metrics": {
                                    "quality": 7,
                                    "architecture": 6,
                                    "standards": 8,
                                    "principles": 7,
                                },
                                "style": "Pre-Junior",
                                "wishes": "Добавьте обработку ошибок.",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

        draft = generate_ai_review_draft(self.project)

        self.assertFalse(draft.status)
        self.assertFalse(draft.is_published)
        self.assertTrue(draft.is_ai_generated)
        self.assertEqual(draft.ai_generation_status, "ready")
        self.assertEqual(draft.amount_problems, 1)
        self.assertEqual(draft.code_quality, 7)
        self.assertIn("&lt;script&gt;", draft.problems)
        self.assertNotIn("<script>", draft.problems)
        self.assertNotIn("Как улучшить", draft.problems)
        self.assertNotIn("Строка 3", draft.problems)
        self.assertIn("<ol", draft.problems)
        self.assertNotIn("<ul", draft.problems)
        self.assertEqual(draft.ai_source_summary, "Передано 1 из 1 Python-файлов, 14 символов")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "gpt-4o-mini")
        self.assertEqual(post.call_args.kwargs["json"]["max_completion_tokens"], 850)
        collect_source.assert_called_once_with(self.project.github)

    @override_settings(PROXYAPI_API_KEY="")
    @patch("codereview.ai_review.collect_repository_source")
    def test_missing_proxyapi_key_records_admin_only_failure(self, collect_source):
        draft = generate_ai_review_draft(self.project)

        self.assertFalse(draft.is_published)
        self.assertEqual(draft.ai_generation_status, "failed")
        self.assertIn("PROXYAPI_API_KEY", draft.ai_generation_error)
        collect_source.assert_not_called()
