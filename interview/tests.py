from datetime import timedelta
from io import BytesIO
import json
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from interview.answer import get_questions, mark_questions_as_shown
from interview.admin import MockInterviewAdmin
from interview.ai_analysis import _repository_files, analyze_mock_interview
from interview.mock_interview import (
    create_mock_interview,
    mock_interview_availability,
    questions_on_cooldown,
)
from interview.models import (
    InterviewQuestion,
    InterviewQuestionCategory,
    InterviewQuestionProgress,
    LiveCodingTask,
    MockInterview,
    MockInterviewAnswer,
    MockInterviewFile,
    MockInterviewSettings,
)
from Course.models import LearnGroup, Student


class InterviewViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='interview-test-user',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.python, _ = InterviewQuestionCategory.objects.get_or_create(
            title='Python',
        )
        self.hr, _ = InterviewQuestionCategory.objects.get_or_create(title='HR')
        InterviewQuestion.objects.all().delete()

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
            return self.client.get('/interview/', params, follow=True)

    def test_categories_are_ordered_by_popularity_then_alphabetically(self):
        InterviewQuestion.objects.all().delete()
        InterviewQuestionCategory.objects.all().delete()
        InterviewQuestionCategory.objects.bulk_create([
            InterviewQuestionCategory(title=title)
            for title in ('Редкая тема', 'Flask', 'Python', 'Django', 'ООП',
                          'HR’ские', 'FastAPI', 'Абстрактная тема')
        ])

        response = self.get_as_student({})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [category.title for category in response.context['categories']],
            [
                'HR’ские',
                'Python',
                'ООП',
                'Django',
                'FastAPI',
                'Flask',
                'Абстрактная тема',
                'Редкая тема',
            ],
        )

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

    def test_question_batch_does_not_change_when_page_is_refreshed(self):
        response = self.get_as_student({
            'amount': 10,
            'technologies': 'random',
        })
        batch_token = response.context['batch_token']
        original_ids = [
            question.pk for question in response.context['question']
        ]
        original_show_counts = dict(
            InterviewQuestionProgress.objects.filter(
                user=self.user,
                question_id__in=original_ids,
            ).values_list('question_id', 'shown_count')
        )

        refreshed = self.get_as_student({'batch': batch_token})

        self.assertEqual(
            [question.pk for question in refreshed.context['question']],
            original_ids,
        )
        self.assertEqual(
            dict(
                InterviewQuestionProgress.objects.filter(
                    user=self.user,
                    question_id__in=original_ids,
                ).values_list('question_id', 'shown_count')
            ),
            original_show_counts,
        )

    def test_regenerate_creates_new_signed_batch_without_server_history(self):
        params = {'amount': 10, 'technologies': 'random'}
        first_response = self.get_as_student(params)

        second_response = self.get_as_student({**params, 'regenerate': 1})

        self.assertNotEqual(
            first_response.context['batch_token'],
            second_response.context['batch_token'],
        )
        self.assertNotIn('interview_question_batches', self.client.session)
        self.assertContains(
            second_response,
            'data-history-key="interview-question-batches-',
            html=False,
        )

    def test_modified_question_batch_token_is_rejected(self):
        response = self.get_as_student({
            'amount': 10,
            'technologies': 'random',
        })

        modified_response = self.get_as_student({
            'batch': f'{response.context["batch_token"]}modified',
        })

        self.assertTemplateUsed(modified_response, 'interview/index.html')

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


class MockInterviewFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('mock-student', password='password')
        self.client.force_login(self.user)
        self.django = InterviewQuestionCategory.objects.get(title='Django')
        self.flask = InterviewQuestionCategory.objects.get(title='Flask')

    def test_live_coding_catalog_has_five_tasks_per_category_and_level(self):
        for category in LiveCodingTask.Category.values:
            for level in LiveCodingTask.Level.values:
                with self.subTest(category=category, level=level):
                    self.assertEqual(
                        LiveCodingTask.objects.filter(
                            category=category,
                            level=level,
                            is_active=True,
                        ).count(),
                        5,
                    )

    def create_interview(
        self,
        *frameworks,
        level=MockInterview.Level.JUNIOR,
        live_coding_category='random',
    ):
        return create_mock_interview(
            self.user,
            frameworks or (self.django,),
            level,
            live_coding_category,
        )

    @patch('interview.views._active_student', return_value=SimpleNamespace())
    def test_start_page_renders_mock_interview_entry(self, active_student):
        response = self.client.get(reverse('mock_interview_start'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовое собеседование')
        self.assertContains(response, 'Django')
        self.assertContains(response, 'FastAPI')
        self.assertContains(response, 'Выберите категорию задачи')
        self.assertContains(response, 'Случайная категория')
        self.assertContains(response, 'Алгоритмы')
        self.assertContains(response, 'Осталось попыток: 3 из 3')
        self.assertContains(
            response,
            '<body class="interview-page mock-interview-page">',
            html=False,
        )

    def test_weekly_limit_blocks_fourth_started_interview(self):
        settings_object = MockInterviewSettings.load()
        settings_object.weekly_attempt_limit = 3
        settings_object.save(update_fields=('weekly_attempt_limit', 'updated_at'))
        for _ in range(3):
            MockInterview.objects.create(
                user=self.user,
                status=MockInterview.Status.ABANDONED,
            )

        availability = mock_interview_availability(self.user)

        self.assertFalse(availability.can_start)
        self.assertEqual(availability.used, 3)
        self.assertEqual(availability.remaining, 0)
        self.assertIsNotNone(availability.next_available_at)
        with self.assertRaisesMessage(ValidationError, 'не более 3'):
            self.create_interview()

    def test_attempt_older_than_seven_days_does_not_use_limit(self):
        settings_object = MockInterviewSettings.load()
        settings_object.weekly_attempt_limit = 1
        settings_object.save(update_fields=('weekly_attempt_limit', 'updated_at'))
        old_interview = MockInterview.objects.create(
            user=self.user,
            status=MockInterview.Status.ABANDONED,
        )
        MockInterview.objects.filter(pk=old_interview.pk).update(
            started_at=timezone.now() - timedelta(days=8),
        )

        availability = mock_interview_availability(self.user)
        interview = self.create_interview()

        self.assertTrue(availability.can_start)
        self.assertEqual(availability.remaining, 1)
        self.assertEqual(interview.user, self.user)

    @patch('interview.views._active_student', return_value=SimpleNamespace())
    def test_start_page_explains_exhausted_weekly_limit(self, active_student):
        settings_object = MockInterviewSettings.load()
        settings_object.weekly_attempt_limit = 1
        settings_object.save(update_fields=('weekly_attempt_limit', 'updated_at'))
        MockInterview.objects.create(
            user=self.user,
            status=MockInterview.Status.ABANDONED,
        )

        response = self.client.get(reverse('mock_interview_start'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Лимит попыток исчерпан')
        self.assertContains(response, 'Вы использовали 1 из 1 попыток')
        self.assertNotContains(
            response,
            'type="submit">Начать собеседование</button>',
            html=False,
        )

    def test_selection_uses_only_curated_questions_and_required_blocks(self):
        interview = self.create_interview(self.django, self.flask)
        answers = list(interview.answers.select_related('original_question'))

        self.assertEqual(len(answers), 18)
        self.assertEqual(
            sum(item.section == MockInterviewAnswer.Section.GENERAL for item in answers),
            4,
        )
        self.assertEqual(
            sum(item.section == MockInterviewAnswer.Section.PYTHON for item in answers),
            5,
        )
        self.assertEqual(
            sum(item.section == MockInterviewAnswer.Section.OOP for item in answers),
            3,
        )
        self.assertEqual(
            sum(item.section == MockInterviewAnswer.Section.FRAMEWORK for item in answers),
            6,
        )
        self.assertTrue(all(item.original_question.use_in_mock for item in answers))
        framework_categories = {
            item.category_snapshot
            for item in answers
            if item.section == MockInterviewAnswer.Section.FRAMEWORK
        }
        self.assertEqual(framework_categories, {'Django', 'Flask'})

    def test_selection_uses_only_questions_for_selected_level(self):
        for level in MockInterview.Level.values:
            interview = self.create_interview(level=level)

            self.assertEqual(interview.level, level)
            expected_task_level = (
                LiveCodingTask.Level.JUNIOR
                if level == MockInterview.Level.JUNIOR
                else LiveCodingTask.Level.MIDDLE
            )
            self.assertEqual(interview.live_coding_task.level, expected_task_level)
            self.assertIn(
                interview.live_coding_task.category,
                LiveCodingTask.Category.values,
            )
            self.assertFalse(
                interview.answers.exclude(original_question__mock_level=level).exists(),
            )

    def test_live_coding_task_is_never_repeated_for_same_student(self):
        first_interview = self.create_interview()

        second_interview = self.create_interview()

        self.assertNotEqual(
            first_interview.live_coding_task_id,
            second_interview.live_coding_task_id,
        )

    def test_student_can_choose_live_coding_category(self):
        interview = self.create_interview(
            live_coding_category=LiveCodingTask.Category.OOP,
        )

        self.assertEqual(
            interview.live_coding_task.category,
            LiveCodingTask.Category.OOP,
        )

    def test_invalid_live_coding_category_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            'Выберите корректную категорию задачи',
        ):
            self.create_interview(live_coding_category='invalid')

    def test_live_coding_task_used_by_another_student_remains_available(self):
        only_task = LiveCodingTask.objects.filter(
            category=LiveCodingTask.Category.PYTHON,
            level=LiveCodingTask.Level.JUNIOR,
        ).first()
        LiveCodingTask.objects.exclude(pk=only_task.pk).update(is_active=False)
        other_user = User.objects.create_user(
            'another-mock-student',
            password='password',
        )
        MockInterview.objects.create(
            user=other_user,
            live_coding_task=only_task,
        )

        interview = self.create_interview()

        self.assertEqual(interview.live_coding_task_id, only_task.pk)

    def test_exhausted_live_coding_pool_does_not_repeat_task(self):
        only_task = LiveCodingTask.objects.filter(
            category=LiveCodingTask.Category.PYTHON,
            level=LiveCodingTask.Level.JUNIOR,
        ).first()
        LiveCodingTask.objects.filter(
            level=LiveCodingTask.Level.JUNIOR,
            category__in=LiveCodingTask.Category.values,
        ).exclude(pk=only_task.pk).update(is_active=False)
        first_interview = self.create_interview()

        with self.assertRaisesMessage(
            ValidationError,
            'Вы уже проходили все доступные задания',
        ):
            self.create_interview()

        self.assertEqual(first_interview.live_coding_task_id, only_task.pk)
        self.assertEqual(MockInterview.objects.filter(user=self.user).count(), 1)

    def test_recently_assessed_questions_are_not_selected_again(self):
        first_interview = self.create_interview()
        excluded_answers = [
            first_interview.answers.filter(
                section=MockInterviewAnswer.Section.GENERAL,
            ).first(),
            first_interview.answers.filter(
                section=MockInterviewAnswer.Section.FRAMEWORK,
            ).first(),
        ]
        excluded_answers[0].result = MockInterviewAnswer.Result.GOOD
        excluded_answers[1].result = MockInterviewAnswer.Result.WRONG
        MockInterviewAnswer.objects.bulk_update(excluded_answers, ('result',))
        first_interview.status = MockInterview.Status.COMPLETED
        first_interview.completed_at = timezone.now()
        first_interview.save(update_fields=('status', 'completed_at'))

        next_interview = self.create_interview()
        selected_ids = set(
            next_interview.answers.values_list('original_question_id', flat=True),
        )

        self.assertTrue(all(
            answer.original_question_id not in selected_ids
            for answer in excluded_answers
        ))

    def test_cooldown_depends_on_answer_result(self):
        now = timezone.now()
        questions = list(
            InterviewQuestion.objects.filter(use_in_mock=True)[:4],
        )
        cases = (
            (MockInterviewAnswer.Result.GOOD, 13),
            (MockInterviewAnswer.Result.PARTIAL, 8),
            (MockInterviewAnswer.Result.WRONG, 1),
        )
        for position, (question, case) in enumerate(zip(questions, cases), start=1):
            result, age_days = case
            interview = MockInterview.objects.create(
                user=self.user,
                status=MockInterview.Status.COMPLETED,
                completed_at=now - timedelta(days=age_days),
            )
            MockInterviewAnswer.objects.create(
                interview=interview,
                original_question=question,
                section=question.mock_section,
                category_snapshot=question.theme.title,
                question_snapshot=question.title,
                result=result,
                position=position,
            )

        for result, age_days in (
            (MockInterviewAnswer.Result.GOOD, 5),
            (MockInterviewAnswer.Result.WRONG, 3),
        ):
            interview = MockInterview.objects.create(
                user=self.user,
                status=MockInterview.Status.COMPLETED,
                completed_at=now - timedelta(days=age_days),
            )
            MockInterviewAnswer.objects.create(
                interview=interview,
                original_question=questions[3],
                section=questions[3].mock_section,
                category_snapshot=questions[3].theme.title,
                question_snapshot=questions[3].title,
                result=result,
                position=1,
            )

        blocked_ids = questions_on_cooldown(self.user, now=now)

        self.assertIn(questions[0].pk, blocked_ids)
        self.assertNotIn(questions[1].pk, blocked_ids)
        self.assertIn(questions[2].pk, blocked_ids)
        self.assertNotIn(questions[3].pk, blocked_ids)

    @patch('interview.views._active_student', return_value=SimpleNamespace())
    def test_student_can_start_and_submit_theory(self, active_student):
        response = self.client.post(
            reverse('mock_interview_start'),
            {
                'level': MockInterview.Level.MIDDLE,
                'frameworks': [self.django.pk],
            },
        )
        interview = MockInterview.objects.get(user=self.user)

        self.assertRedirects(
            response,
            reverse('mock_interview_theory', args=(interview.pk,)),
        )
        payload = {
            f'answer_{answer.pk}': f'Ответ {answer.position}'
            for answer in interview.answers.all()
        }
        response = self.client.post(
            reverse('mock_interview_theory', args=(interview.pk,)),
            payload,
        )
        interview.refresh_from_db()
        self.assertRedirects(
            response,
            reverse('mock_interview_live_coding', args=(interview.pk,)),
        )
        self.assertEqual(interview.status, MockInterview.Status.LIVE_CODING)
        self.assertEqual(interview.level, MockInterview.Level.MIDDLE)
        self.assertTrue(interview.theory_completed_at)
        self.assertFalse(interview.answers.filter(answer_text='').exists())

    @patch('interview.views._active_student', return_value=SimpleNamespace())
    def test_theory_requires_every_answer(self, active_student):
        interview = self.create_interview()
        first = interview.answers.first()

        response = self.client.post(
            reverse('mock_interview_theory', args=(interview.pk,)),
            {f'answer_{first.pk}': 'Только один ответ'},
        )

        interview.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ответьте на все вопросы')
        self.assertEqual(interview.status, MockInterview.Status.THEORY)

    @patch('interview.views._active_student', return_value=SimpleNamespace())
    def test_live_coding_saves_private_file_and_starts_analysis(self, active_student):
        with tempfile.TemporaryDirectory() as directory, override_settings(
            PRIVATE_SOLUTION_MEDIA_ROOT=directory,
        ):
            interview = self.create_interview()
            interview.status = MockInterview.Status.LIVE_CODING
            interview.save(update_fields=('status',))

            response = self.client.post(
                reverse('mock_interview_live_coding', args=(interview.pk,)),
                {
                    'solution': 'def solve():\n    return True',
                    'files': SimpleUploadedFile('solution.py', b'print("ok")'),
                },
            )

            interview.refresh_from_db()
            solution_file = interview.solution_files.get()
            self.assertRedirects(
                response,
                reverse('mock_interview_processing', args=(interview.pk,)),
            )
            self.assertEqual(interview.status, MockInterview.Status.ANALYZING)
            self.assertEqual(solution_file.original_name, 'solution.py')
            self.assertNotIn('solution.py', solution_file.file.name)

    @patch('interview.views._active_student', return_value=SimpleNamespace())
    def test_live_coding_accepts_repository_url_without_text_or_file(
        self,
        active_student,
    ):
        interview = self.create_interview()
        interview.status = MockInterview.Status.LIVE_CODING
        interview.save(update_fields=('status',))

        response = self.client.post(
            reverse('mock_interview_live_coding', args=(interview.pk,)),
            {'repository_url': 'https://github.com/example/mock-solution'},
        )

        interview.refresh_from_db()
        self.assertRedirects(
            response,
            reverse('mock_interview_processing', args=(interview.pk,)),
        )
        self.assertEqual(
            interview.live_coding_repository_url,
            'https://github.com/example/mock-solution',
        )

    @patch('interview.views._active_student', return_value=SimpleNamespace())
    def test_live_coding_and_processing_pages_render(self, active_student):
        interview = self.create_interview()
        interview.status = MockInterview.Status.LIVE_CODING
        interview.save(update_fields=('status',))

        live_response = self.client.get(
            reverse('mock_interview_live_coding', args=(interview.pk,)),
        )
        interview.status = MockInterview.Status.ANALYZING
        interview.save(update_fields=('status',))
        processing_response = self.client.get(
            reverse('mock_interview_processing', args=(interview.pk,)),
        )

        self.assertEqual(live_response.status_code, 200)
        self.assertContains(live_response, 'Завершить и отправить на разбор')
        self.assertContains(
            live_response,
            interview.live_coding_task.get_category_display(),
        )
        self.assertContains(
            live_response,
            interview.live_coding_task.get_level_display(),
        )
        self.assertEqual(processing_response.status_code, 200)
        self.assertContains(processing_response, 'Разбираем собеседование')
        self.assertIn('csrftoken', processing_response.cookies)

    def test_other_user_cannot_open_result(self):
        interview = self.create_interview()
        interview.status = MockInterview.Status.COMPLETED
        interview.save(update_fields=('status',))
        other = User.objects.create_user('other-mock-user', password='password')
        self.client.force_login(other)

        response = self.client.get(
            reverse('mock_interview_result', args=(interview.pk,)),
        )

        self.assertEqual(response.status_code, 404)

    def test_student_can_abandon_unfinished_attempt(self):
        interview = self.create_interview()

        response = self.client.post(
            reverse('mock_interview_abandon', args=(interview.pk,)),
        )

        interview.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('mock_interview_start'))
        self.assertEqual(interview.status, MockInterview.Status.ABANDONED)

    def test_completed_result_page_renders_scores_and_wrong_comment(self):
        interview = self.create_interview()
        interview.status = MockInterview.Status.COMPLETED
        interview.theory_score = 70
        interview.live_coding_score = 80
        interview.overall_score = 73
        interview.summary = 'Нужно укрепить несколько тем.'
        interview.strengths = ['Python']
        interview.weaknesses = ['HTTP']
        interview.live_coding_repository_url = (
            'https://github.com/example/mock-solution'
        )
        interview.save(update_fields=(
            'status', 'theory_score', 'live_coding_score', 'overall_score',
            'summary', 'strengths', 'weaknesses',
            'live_coding_repository_url',
        ))
        answer = interview.answers.first()
        answer.answer_text = 'Неточный ответ'
        answer.result = MockInterviewAnswer.Result.WRONG
        answer.ai_comment = 'Повторите определение.'
        answer.save(update_fields=('answer_text', 'result', 'ai_comment'))

        response = self.client.get(
            reverse('mock_interview_result', args=(interview.pk,)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '73%')
        self.assertContains(response, 'Повторите определение.')
        self.assertContains(response, 'Открыть Git-репозиторий')

    @patch('interview.views._active_student', return_value=SimpleNamespace())
    def test_history_page_contains_only_completed_own_interviews(
        self,
        active_student,
    ):
        completed = self.create_interview(level=MockInterview.Level.SENIOR)
        completed.status = MockInterview.Status.COMPLETED
        completed.overall_score = 81
        completed.save(update_fields=('status', 'overall_score'))
        self.create_interview(level=MockInterview.Level.MIDDLE)
        other_user = User.objects.create_user('history-other-user')
        hidden = MockInterview.objects.create(
            user=other_user,
            status=MockInterview.Status.COMPLETED,
            overall_score=99,
        )

        response = self.client.get(reverse('mock_interview_history'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '81%')
        self.assertContains(response, 'Senior')
        self.assertNotContains(response, '99%')
        self.assertContains(
            response,
            reverse('mock_interview_result', args=(completed.pk,)),
        )
        self.assertNotContains(
            response,
            reverse('mock_interview_result', args=(hidden.pk,)),
        )


class MockInterviewAnalysisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('analysis-user')
        django = InterviewQuestionCategory.objects.get(title='Django')
        self.interview = create_mock_interview(self.user, (django,))
        self.interview.live_coding_answer = 'print("ready")'
        self.interview.status = MockInterview.Status.ANALYZING
        self.interview.save(update_fields=('live_coding_answer', 'status'))
        self.answers = list(self.interview.answers.all())
        for answer in self.answers:
            answer.answer_text = f'Ответ на вопрос {answer.position}'
        MockInterviewAnswer.objects.bulk_update(self.answers, ('answer_text',))

    @override_settings(
        PROXYAPI_API_KEY='test-key',
        PROXYAPI_MOCK_INTERVIEW_MODEL='test-model',
        PROXYAPI_REVIEW_API_URL='https://example.invalid/v1/chat/completions',
    )
    @patch('interview.ai_analysis.requests.post')
    def test_analysis_saves_scores_and_comments_only_for_wrong_answers(self, post):
        assessments = []
        for index, answer in enumerate(self.answers):
            result = ('wrong' if index == 0 else 'partial' if index == 1 else 'good')
            assessments.append({
                'id': answer.pk,
                'result': result,
                'comment': 'Разберите тему подробнее',
            })
        post.return_value = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            'theory_score': 76,
                            'live_coding_score': 90,
                            'summary': 'Хорошая база.',
                            'strengths': ['Python'],
                            'weaknesses': ['Первый вопрос'],
                            'live_coding_comment': 'Рабочее решение.',
                            'answers': assessments,
                        }),
                    },
                }],
            },
        )

        analyze_mock_interview(self.interview)

        self.interview.refresh_from_db()
        wrong = self.interview.answers.get(pk=self.answers[0].pk)
        partial = self.interview.answers.get(pk=self.answers[1].pk)
        good = self.interview.answers.get(pk=self.answers[2].pk)
        self.assertEqual(self.interview.status, MockInterview.Status.COMPLETED)
        self.assertEqual(self.interview.overall_score, 80)
        self.assertEqual(wrong.ai_comment, 'Разберите тему подробнее')
        self.assertEqual(partial.ai_comment, '')
        self.assertEqual(good.ai_comment, '')

    @patch('interview.ai_analysis.requests.get')
    def test_public_github_repository_files_are_included_safely(self, get):
        archive = BytesIO()
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('project-main/app.py', 'print("from repository")')
            zipped.writestr('project-main/image.png', b'not source code')
        get.return_value = SimpleNamespace(
            raise_for_status=lambda: None,
            iter_content=lambda chunk_size: [archive.getvalue()],
        )

        content = _repository_files(
            'https://github.com/example/mock-solution',
        )

        self.assertIn('Файл репозитория: project-main/app.py', content)
        self.assertIn('print("from repository")', content)
        self.assertNotIn('image.png', content)


class MockInterviewTeacherAccessTests(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            'mock-teacher', password='password', is_staff=True,
        )
        teacher = Student.objects.create(
            user=self.teacher_user,
            contact='@teacher',
            is_learned=False,
            groups_id=910,
        )
        self.group = LearnGroup.objects.create(
            pk=910,
            title='Группа мок-собеседований',
            teacher=teacher,
            is_studies=True,
        )
        self.student_user = User.objects.create_user('teacher-student')
        Student.objects.create(
            user=self.student_user,
            contact='@student',
            is_learned=True,
            groups=self.group,
        )
        self.other_user = User.objects.create_user('outside-student')
        self.visible = MockInterview.objects.create(user=self.student_user)
        self.hidden = MockInterview.objects.create(user=self.other_user)

    def test_teacher_admin_history_contains_only_own_students(self):
        request = RequestFactory().get('/coursemc_control/interview/mockinterview/')
        request.user = self.teacher_user
        model_admin = MockInterviewAdmin(MockInterview, admin.site)

        queryset = model_admin.get_queryset(request)

        self.assertEqual(set(queryset), {self.visible})
