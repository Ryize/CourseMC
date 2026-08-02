from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

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
