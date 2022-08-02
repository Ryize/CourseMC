from django.contrib.auth.models import User
from django.test import TestCase

from blog.models import Post, Comment, Category


class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test', password='1234')
        self.category = Category.objects.create(title='Тестовое название категории')
        self.post = Post.objects.create(title='Тестовое название', description='Тестовое описание',
                                        content='Тестовый контент', author=self.user)
        self.post.categories.set([self.category])
        self.comment = Comment.objects.create(comment='Комментарий к тестовому посту', author=self.user, post=self.post)

    def test_category_verbose_name(self):
        """Check verbose_names in Category model."""
        fields_verbose = {
            'title': 'Название категории',
            'color': 'Цвет фона',
            'created_at': 'Создана',
        }
        for field, expected_value in fields_verbose.items():
            with self.subTest(field=field):
                self.assertEquals(
                    self.category._meta.get_field(field).verbose_name,
                    expected_value,
                )

    def test_post_page_verbose_name(self):
        """Check verbose_names in Post model."""
        fields_verbose = {
            'title': 'Название',
            'description': 'Описание',
            'content': 'Текст поста',
            'author': 'Автор',
            'image': 'Изображение',
            'is_displayed': 'Отображается',
            'categories': 'Категории',
            'created_at': 'Создан',
        }
        for field, expected_value in fields_verbose.items():
            with self.subTest(field=field):
                self.assertEquals(
                    self.post._meta.get_field(field).verbose_name,
                    expected_value,
                )

    def test_comment_verbose_name(self):
        """Check verbose_names in Comment model."""
        fields_verbose = {
            'comment': 'Комментарий',
            'author': 'Автор',
            'post': 'Пост',
            'created_at': 'Написан',
        }
        for field, expected_value in fields_verbose.items():
            with self.subTest(field=field):
                self.assertEquals(
                    self.comment._meta.get_field(field).verbose_name,
                    expected_value,
                )

    def test__str__(self):
        """Check __str__ in all models."""
        fields_str = {
            f'{self.category}': f'{self.category.title}',
            f'{self.post}': f'{self.post.title}, {self.post.author}',
            f'{self.comment}': f'{self.comment.comment}, {self.comment.post}',
        }
        for field, expected_object_name in fields_str.items():
            with self.subTest(field=field):
                self.assertEquals(expected_object_name, str(field))

    def test_get_absolute_url_article(self):
        """Check get_absolute_url in Article model."""
        self.assertEquals(self.post.get_absolute_url(), '/blog/post/1')
