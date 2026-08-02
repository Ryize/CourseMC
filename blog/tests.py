from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Post


class PostAccessTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", password="password")
        self.other = User.objects.create_user("reader", password="password")
        self.post = Post.objects.create(
            title="Черновик",
            description="Не опубликован",
            content="Содержимое",
            author=self.author,
            is_displayed=False,
        )

    def test_unpublished_post_is_visible_only_to_author_or_staff(self):
        url = reverse("post_view", args=(self.post.pk,))
        anonymous_response = self.client.get(url)
        self.client.force_login(self.other)
        other_response = self.client.get(url)
        self.client.force_login(self.author)
        author_response = self.client.get(url)

        self.assertEqual(anonymous_response.status_code, 404)
        self.assertEqual(other_response.status_code, 404)
        self.assertEqual(author_response.status_code, 200)
