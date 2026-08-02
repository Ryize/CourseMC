from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Category, TodoListUser


class TodoAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("todo-user", password="password")
        self.other = User.objects.create_user("todo-other", password="password")
        self.category = Category.objects.create(title="Общее")

    def test_user_cannot_delete_another_users_task(self):
        own_task = TodoListUser.objects.create(
            title="Своя задача",
            content="Своя",
            category=self.category,
            user=self.user,
        )
        other_task = TodoListUser.objects.create(
            title="Чужая задача",
            content="Чужая",
            category=self.category,
            user=self.other,
        )
        self.client.force_login(self.user)

        self.client.post(
            reverse("todo"),
            {
                "task_delete": "1",
                "checked_box": [own_task.pk, other_task.pk],
            },
        )

        self.assertFalse(TodoListUser.objects.filter(pk=own_task.pk).exists())
        self.assertTrue(TodoListUser.objects.filter(pk=other_task.pk).exists())
