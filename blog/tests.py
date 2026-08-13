from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware

from .models import Category, Post


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


class PostFilterTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", password="password")
        self.python = Category.objects.create(title="Python")
        self.unused = Category.objects.create(title="Не используется")

    def test_public_list_uses_categories_of_published_posts(self):
        published = Post.objects.create(
            title="Опубликованная статья",
            description="Описание",
            content="Содержимое",
            author=self.author,
            is_displayed=True,
        )
        published.categories.add(self.python)

        response = self.client.get(reverse("blog_home"))

        self.assertContains(response, 'data-blog-filter="Python"')
        self.assertNotContains(response, 'data-blog-filter="Не используется"')
        self.assertNotContains(response, "Новая тема")
        self.assertNotContains(response, "Ключевая тема")

    def test_my_posts_filter_includes_categories_from_drafts(self):
        draft = Post.objects.create(
            title="Черновик",
            description="Описание",
            content="Содержимое",
            author=self.author,
            is_displayed=False,
        )
        draft.categories.add(self.python)
        self.client.force_login(self.author)

        response = self.client.get(reverse("my_post"))

        self.assertContains(response, 'data-blog-filter="Python"')


class PostDateFormatTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", password="password")
        self.post = Post.objects.create(
            title="Статья с датой",
            description="Описание",
            content="Содержимое",
            author=self.author,
            is_displayed=True,
        )
        Post.objects.filter(pk=self.post.pk).update(
            created_at=make_aware(datetime(2024, 2, 11, 22, 22))
        )
        self.post.refresh_from_db()

    def test_publication_date_format_in_list_and_detail(self):
        expected_date = "11 февраля 2024 г. 22:22"

        list_response = self.client.get(reverse("blog_home"))
        detail_response = self.client.get(
            reverse("post_view", args=(self.post.pk,))
        )

        self.assertContains(list_response, expected_date)
        self.assertContains(detail_response, expected_date)
