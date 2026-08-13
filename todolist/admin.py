# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import TodoListUser, TodoListGroup, Category


class TodoListUserAdmin(ModelAdmin):
    list_display = ("title", "created_at", "due_date",)


class TodoListGroupAdmin(ModelAdmin):
    list_display = ("title", "created_at", "due_date",)


class CategoryAdmin(ModelAdmin):
    list_display = ("title",)


admin.site.register(TodoListUser, TodoListUserAdmin)
admin.site.register(TodoListGroup, TodoListGroupAdmin)
admin.site.register(Category, CategoryAdmin)
