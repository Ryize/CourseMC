from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin
from django.db.models import Count
from django.utils.safestring import mark_safe

from CourseMC.widgets import RichTextEditorWidget

from .models import *


class AuthorListFilter(admin.SimpleListFilter):
    """
    Фильтр для авторов поста в админ-панели блога.

    Позволяет добавлять в фильтр только тех, кто написал хотя бы один пост.
    """

    title = 'Авторы'

    parameter_name = 'user'

    model = Post

    def lookups(self, request, model_admin) -> tuple:
        """
        Возвращает список кортежей, данные из которых будут отображаться в
        фильтре.

        Returns:
            tuple:
            [i][0] - закодированное значение параметра, которое будет
            отображаться в URL-запросе.
            [i][1] - удобочитаемое имя параметра, которое появится на правой
            боковой панели.
        """
        authors = (
            self.model.objects
            .order_by('author__username')
            .values_list('author__username', flat=True)
            .distinct()
        )
        return tuple((username, username) for username in authors)

    def queryset(self, request, queryset):
        """
        Фильтрует запрос.

        Returns:
            queryset: Отфильтрованный набор запросов на основе значения,
            указанного в строке запроса, которое можно получить с помощью
            `self.value()`.
        """
        if not self.value():
            return queryset
        post = self.model.objects.filter(author__username=self.value()).first()
        if not post:
            return queryset
        return queryset.filter(author=post.author)


class PostListFilter(admin.SimpleListFilter):
    """
    Фильтр для пользователей в админ-панели списка платежей
    (InformationPaymentsAdmin).

    Позволяет добавлять в стандартный фильтр только тех, кто оплатил хотя бы
    раз.
    """

    title = 'Посты'

    parameter_name = 'post'

    def lookups(self, request, model_admin) -> tuple:
        """
        Возвращает список кортежей, данные из которых будут отображаться в
        фильтре.

        Returns:
            tuple:
            [i][0] - закодированное значение параметра, которое будет
            отображаться в URL-запросе.
            [i][1] - удобочитаемое имя параметра, которое появится на правой
            боковой панели.
        """
        posts = (
            Comment.objects
            .order_by('post__title')
            .values_list('post__title', flat=True)
            .distinct()
        )
        return tuple((title, title) for title in posts)

    def queryset(self, request, queryset):
        """
        Фильтрует запрос.

        Returns:
            queryset: Отфильтрованный набор запросов на основе значения,
            указанного в строке запроса, которое можно получить с помощью
            `self.value()`.
        """
        if not self.value():
            return queryset
        return queryset.filter(post__title=self.value())


class CommentAuthorListFilter(AuthorListFilter):
    model = Comment


@admin.register(Post)
class PostAdmin(ModelAdmin):
    content = forms.CharField(widget=RichTextEditorWidget())
    fields = (
        "title",
        "description",
        "content",
        "author",
        "categories",
        "is_displayed",
        "image",
    )
    list_display = (
        "title",
        "author",
        "created_at",
        "is_displayed",
        "get_image",
    )
    list_display_links = (
        "title",
        "author",
        "created_at",
    )
    list_filter = (
        AuthorListFilter,
        "is_displayed",
    )
    empty_value_display = "-пустой-"
    list_per_page = 64
    list_max_show_all = 8
    search_fields = (
        "title",
        "description",
        "content",
        "author",
        "created_at",
    )
    date_hierarchy = "created_at"

    def get_image(self, obj):
        return mark_safe(f"<img src='{obj.image.url}' width='75' height='75'>")

    get_image.short_description = "Изображение"


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    fields = (
        "comment",
        "author",
        "post",
    )
    list_display = (
        "comment",
        "author",
        "post",
    )
    list_display_links = (
        "comment",
        "author",
        "post",
    )
    list_filter = (
        CommentAuthorListFilter,
        PostListFilter,
    )
    empty_value_display = "-пустой-"
    list_per_page = 64
    list_max_show_all = 8
    search_fields = (
        "author",
        "post",
    )
    date_hierarchy = "created_at"


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    fields = (
        "title",
        "color",
    )
    list_display = (
        "title",
        "created_at",
    )
    list_display_links = (
        "title",
        "created_at",
    )
    empty_value_display = "-пустой-"
    list_per_page = 64
    list_max_show_all = 8
    search_fields = (
        "title",
        "created_at",
    )
    date_hierarchy = "created_at"
