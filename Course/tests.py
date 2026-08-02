from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    AdditionalLessons,
    DirectionStudy,
    LearnGroup,
    Schedule,
    Student,
)


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
