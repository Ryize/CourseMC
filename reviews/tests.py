from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Review


class ReviewSubmissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("reviewer", password="password")

    def test_anonymous_and_empty_reviews_are_rejected(self):
        url = reverse("review")
        anonymous_response = self.client.post(url, {"content": "Отзыв"})
        self.client.force_login(self.user)
        empty_response = self.client.post(url, {"content": "  "})

        self.assertEqual(anonymous_response.status_code, 401)
        self.assertEqual(empty_response.status_code, 400)
        self.assertFalse(Review.objects.exists())

    def test_user_can_submit_only_one_review(self):
        self.client.force_login(self.user)
        url = reverse("review")

        first_response = self.client.post(url, {"content": "Первый отзыв"})
        second_response = self.client.post(url, {"content": "Второй отзыв"})

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.json()["error_code"], 1)
        self.assertEqual(Review.objects.filter(author_id=self.user).count(), 1)

    def test_reviews_are_paginated_and_newest_are_first(self):
        now = timezone.now()
        for index in range(17):
            author = User.objects.create_user(
                f"reviewer-{index}",
                password="password",
            )
            Review.objects.create(
                author_id=author,
                content=f"Отзыв {index}",
                pub_date=now - timedelta(days=index),
            )

        first_page = self.client.get(reverse("review"), HTTP_HOST="localhost")
        second_page = self.client.get(
            f"{reverse('review')}?page=2",
            HTTP_HOST="localhost",
        )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(
            [review.content for review in first_page.context["reviews"]],
            [f"Отзыв {index}" for index in range(16)],
        )
        self.assertContains(first_page, "?page=2")
        self.assertContains(second_page, "Отзыв 16")
