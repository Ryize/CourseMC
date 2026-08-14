import json
from datetime import timedelta

from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from CourseMC.admin_dashboard import dashboard_callback
from codereview.models import ProjectCategories, ProjectForReview
from interview.models import (
    InterviewQuestion,
    InterviewQuestionCategory,
    InterviewQuestionProgress,
)
from questionnaire.models import (
    AnswerQuestion,
    PassedPolls,
    Question,
    Quiz,
    UserAnswer,
)

from .models import (
    ApplicationsForTraining,
    DirectionStudy,
    LearnGroup,
    LessonSolution,
    LessonSolutionSubmission,
    Schedule,
    Student,
    StudentQuestion,
)


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            'dashboard-admin',
            email='admin@example.com',
            password='password',
        )
        self.teacher_user = User.objects.create_user(
            'dashboard-teacher',
            password='password',
            is_staff=True,
        )
        self.teacher = Student.objects.create(
            user=self.teacher_user,
            contact='@teacher',
            is_learned=False,
            groups_id=901,
        )
        self.group = LearnGroup.objects.create(
            pk=901,
            title='Активная группа',
            teacher=self.teacher,
            is_studies=True,
        )
        self.direction = DirectionStudy.objects.create(title='Dashboard Python')
        self.students = []
        for number in range(3):
            user = User.objects.create_user(
                f'dashboard-student-{number}',
                password='password',
            )
            student = Student.objects.create(
                user=user,
                contact=f'@student{number}',
                groups=self.group,
                is_learned=True,
            )
            student.direction.add(self.direction)
            self.students.append(student)

        self.schedule = Schedule.objects.create(
            theme='Урок для аналитики',
            plan='План',
            lesson_materials='Материалы',
            direction=self.direction,
        )
        self.solution = LessonSolution.objects.create(
            student=self.students[0],
            schedule=self.schedule,
            status=LessonSolution.Status.PENDING,
        )
        now = timezone.now()
        LessonSolutionSubmission.objects.create(
            solution=self.solution,
            attempt_number=1,
            submitted_at=now - timedelta(days=8),
        )
        LessonSolutionSubmission.objects.create(
            solution=self.solution,
            attempt_number=2,
            submitted_at=now - timedelta(days=1),
        )

        self.quiz = Quiz.objects.create(
            title='Python: проверка основ',
            description='Проверка',
            topic='Python',
            lifetime=now + timedelta(days=30),
            user=self.admin_user,
        )
        self.question = Question.objects.create(
            question='Какой ответ верный?',
            quiz=self.quiz,
        )
        correct = AnswerQuestion.objects.create(
            answer='Верный',
            question=self.question,
            correct=True,
        )
        wrong = AnswerQuestion.objects.create(
            answer='Неверный',
            question=self.question,
            correct=False,
        )
        for index, student in enumerate(self.students):
            UserAnswer.objects.create(
                quiz=self.quiz,
                question=self.question,
                answers=correct if index == 0 else wrong,
                user=student.user,
            )
            PassedPolls.objects.create(
                quiz=self.quiz,
                passed_user=student.user,
            )

        category = InterviewQuestionCategory.objects.create(title='Python')
        interview_question = InterviewQuestion.objects.create(
            title='Что такое список?',
            theme=category,
            percent=80,
            complexity=2,
        )
        for index, student in enumerate(self.students):
            InterviewQuestionProgress.objects.create(
                user=student.user,
                question=interview_question,
                status=(
                    InterviewQuestionProgress.Status.ANSWERED
                    if index == 0
                    else InterviewQuestionProgress.Status.REPEAT
                ),
                last_shown_at=now,
                next_available_at=now,
            )

        StudentQuestion.objects.create(
            group=self.group,
            question='Нужна помощь с задачей',
        )
        review_category = ProjectCategories.objects.create(
            title='Учебный проект',
            min_lines=1,
            min_cognetive=1,
            max_cognetive=100,
        )
        ProjectForReview.objects.create(
            category=review_category,
            user=self.students[0],
            github='https://github.com/example/project',
            lines=1,
            cognetive=1,
        )
        ApplicationsForTraining.objects.create(
            student=self.students[1],
            ip='192.0.2.10',
        )

    def dashboard_context(self, user=None, **params):
        request = RequestFactory().get('/coursemc_control/', params)
        request.user = user or self.admin_user
        return dashboard_callback(request, {})

    def test_dashboard_contains_requested_learning_analytics(self):
        context = self.dashboard_context(period=30)

        solution_data = json.loads(context['solution_activity_chart']['data'])
        self.assertEqual(sum(solution_data['datasets'][0]['data']), 1)
        self.assertEqual(sum(solution_data['datasets'][1]['data']), 1)
        self.assertTrue(context['solution_status_chart']['has_data'])
        self.assertTrue(context['quiz_results_chart']['has_data'])
        self.assertTrue(context['difficult_questions_chart']['has_data'])
        self.assertTrue(context['quiz_activity_chart']['has_data'])
        self.assertTrue(context['interview_progress_chart']['has_data'])
        self.assertEqual(context['interview_answered_percent'], 33)

        kpis = {item['title']: item['value'] for item in context['dashboard_kpis']}
        self.assertEqual(kpis['Средний результат'], '33%')
        self.assertNotIn('Платежи', kpis)
        self.assertNotIn('Доход', kpis)

        attention = {item['title']: item['count'] for item in context['attention_sections']}
        self.assertEqual(attention['Решения на проверке'], 1)
        self.assertEqual(attention['Проекты ожидают ревью'], 1)
        self.assertEqual(attention['Нерешённые вопросы'], 1)
        self.assertEqual(attention['Новые заявки'], 1)

    def test_teacher_sees_only_own_active_groups(self):
        context = self.dashboard_context(user=self.teacher_user)

        self.assertEqual(list(context['dashboard_groups']), [self.group])
        self.assertEqual(context['dashboard_kpis'][0]['value'], 3)

    def test_admin_index_renders_unfold_dashboard(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin:index'), {'period': 30})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Обзор платформы')
        self.assertContains(response, 'Требует внимания')
        self.assertContains(response, 'Самые сложные вопросы')
        self.assertContains(response, 'Разделы админки')
        self.assertContains(response, 'myadmins/admin_interactions.css')
        self.assertContains(response, 'myadmins/admin_row_navigation.js')
        self.assertContains(response, 'id="nav-sidebar-apps"')
        self.assertContains(response, 'admin-nav-section')
        document = BeautifulSoup(response.content, 'html.parser')
        self.assertFalse(any(link.find_parent('a') for link in document.find_all('a')))

    def test_admin_change_list_loads_full_row_navigation(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('admin:codereview_projectforreview_changelist'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'myadmins/admin_row_navigation.js')
        self.assertContains(response, 'myadmins/admin_interactions.css')

    def test_admin_app_index_loads_sidebar_assets(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin:app_list', args=('blog',)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'myadmins/admin_interactions.css')
        self.assertContains(response, 'myadmins/admin_row_navigation.js')
        self.assertContains(response, 'id="nav-sidebar-apps"')
        self.assertContains(response, 'admin-nav-section')

    def test_student_admin_does_not_offer_group_filter(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin:Course_student_changelist'))

        self.assertEqual(response.status_code, 200)
        filter_titles = [
            spec.title
            for spec in response.context['cl'].filter_specs
        ]
        self.assertNotIn('Группа обучения', filter_titles)
        self.assertIn('Учащийся', filter_titles)
        self.assertIn('Направление', filter_titles)
