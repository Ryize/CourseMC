# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .models import TodoListUser, TodoListGroup, Category


class TodoListUserAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at", "due_date",)


class TodoListGroupAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at", "due_date",)


class CategoryAdmin(admin.ModelAdmin):
    list_display = ("title",)


admin.site.register(TodoListUser, TodoListUserAdmin)
admin.site.register(TodoListGroup, TodoListGroupAdmin)
admin.site.register(Category, CategoryAdmin)
