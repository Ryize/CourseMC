from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from billing.admin import UserListFilter
from billing.models import InformationPayments
from blog.admin import AuthorListFilter, PostListFilter
from blog.models import Comment, Post
from chatgpt.admin import DecadeBornListFilter, RequestsGPTAdmin
from chatgpt.models import RequestsGPT

from .models import LearnGroup, Student


class FilterOrderingTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get('/admin/')
        self.teacher_user = User.objects.create_user(
            'teacher',
            email='teacher@example.com',
            password='password',
            is_staff=True,
        )
        self.teacher = Student.objects.create(
            user=self.teacher_user,
            contact='@teacher',
            groups_id=500,
        )
        self.group = LearnGroup.objects.create(
            pk=500,
            title='Учебная группа',
            is_studies=True,
            teacher=self.teacher,
        )

    def test_user_filters_are_sorted_alphabetically(self):
        alexey_user = User.objects.create_user(
            'Алексей', email='alexey@example.com',
        )
        alexey = Student.objects.create(
            user=alexey_user,
            contact='@alexey',
            is_learned=True,
            groups=self.group,
        )
        boris_user = User.objects.create_user(
            'Борис', email='boris@example.com',
        )
        boris = Student.objects.create(
            user=boris_user,
            contact='@boris',
            is_learned=True,
            groups=self.group,
        )
        InformationPayments.objects.create(user=boris, amount=1000)
        InformationPayments.objects.create(user=alexey, amount=1000)

        author_z = User.objects.create_user('zeta_author')
        author_a = User.objects.create_user('alpha_author')
        post_z = Post.objects.create(
            title='Яблоко',
            description='Описание',
            content='Текст',
            author=author_z,
        )
        post_a = Post.objects.create(
            title='Арбуз',
            description='Описание',
            content='Текст',
            author=author_a,
        )
        Comment.objects.create(comment='Комментарий', author=author_z, post=post_z)
        Comment.objects.create(comment='Комментарий', author=author_a, post=post_a)

        RequestsGPT.objects.create(
            user=author_z,
            text_request='Запрос',
            text_response='Ответ',
        )
        RequestsGPT.objects.create(
            user=author_a,
            text_request='Запрос',
            text_response='Ответ',
        )
        RequestsGPT.objects.create(
            user=None,
            text_request='Запрос без автора',
            text_response='Ответ',
        )

        payment_filter = UserListFilter(
            self.request,
            {},
            InformationPayments,
            admin.site._registry[InformationPayments],
        )
        author_filter = AuthorListFilter(
            self.request,
            {},
            Post,
            admin.site._registry[Post],
        )
        post_filter = PostListFilter(
            self.request,
            {},
            Comment,
            admin.site._registry[Comment],
        )
        request_filter = DecadeBornListFilter(
            self.request,
            {},
            RequestsGPT,
            RequestsGPTAdmin(RequestsGPT, admin.site),
        )

        self.assertEqual(
            [label for _, label in payment_filter.lookups(self.request, None)],
            ['Алексей', 'Борис'],
        )
        self.assertEqual(
            [label for _, label in author_filter.lookups(self.request, None)],
            ['alpha_author', 'zeta_author'],
        )
        self.assertEqual(
            [label for _, label in post_filter.lookups(self.request, None)],
            ['Арбуз', 'Яблоко'],
        )
        self.assertEqual(
            [label for _, label in request_filter.lookups(self.request, None)],
            ['alpha_author', 'zeta_author'],
        )
