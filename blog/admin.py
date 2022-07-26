from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django import forms
from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import *


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    content = forms.CharField(widget=CKEditorUploadingWidget())
    fields = ('title', 'description', 'content', 'author', 'categories', 'is_displayed', 'image',)
    list_display = ('title', 'description', 'author', 'created_at', 'is_displayed', 'get_image',)
    list_display_links = ('title', 'description', 'author', 'created_at',)
    list_filter = ('author', 'created_at',)
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ('title', 'description', 'content', 'author', 'created_at',)
    date_hierarchy = 'created_at'

    def get_image(self, obj):
        return mark_safe(f"<img src='{obj.image.url}' width='75' height='75'>")

    get_image.short_description = 'Изображение'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    fields = ('comment', 'author', 'post',)
    list_display = ('comment', 'author', 'post',)
    list_display_links = ('comment', 'author', 'post',)
    list_filter = ('author', 'post',)
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ('author', 'post',)
    date_hierarchy = 'created_at'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    fields = ('title', 'color',)
    list_display = ('title', 'created_at',)
    list_display_links = ('title', 'created_at',)
    empty_value_display = '-пустой-'
    list_per_page = 64
    list_max_show_all = 8
    search_fields = ('title', 'created_at',)
    date_hierarchy = 'created_at'
