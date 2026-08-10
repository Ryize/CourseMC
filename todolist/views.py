from typing import Optional

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect

from Course.models import Student
from .models import TodoListUser, Category, TodoListGroup


@login_required
def todo_user(request):
    if request.method == "POST":
        if "task_add" in request.POST:
            if not valid_params(request):
                return redirect("todo")
            TodoListUser.objects.create(**get_request_data(request),
                                        user=request.user,
                                        )
        if "task_delete" in request.POST:
            task_delete(
                request,
                TodoListUser.objects.filter(user=request.user),
            )
        return redirect("todo")
    todos = TodoListUser.objects.filter(user=request.user).all()
    return request_GET(request, todos)


@login_required
def todo_group(request):
    student = Student.objects.for_user(request.user)
    if student is None:
        raise PermissionDenied
    group = student.groups
    if request.method == "POST":
        if "task_add" in request.POST:
            if not valid_params(request):
                return redirect("todo")
            TodoListGroup.objects.create(**get_request_data(request),
                                         group=group,
                                         )
        if "task_delete" in request.POST:
            task_delete(
                request,
                TodoListGroup.objects.filter(group=group),
            )
        return redirect("todo_group")
    todos = TodoListGroup.objects.filter(group=group).all()
    return request_GET(request, todos, group.title)


def valid_params(request):
    title = request.POST.get('description')
    date = str(request.POST.get('date'))
    if not (title and date):
        return False
    return True


def get_request_data(request):
    title = request.POST.get('description')
    date = str(request.POST.get('date'))
    category = request.POST.get('category_select') or 'Общее'
    content = title + " -- " + date + " " + category
    context = {
        'title': title,
        'due_date': date,
        'category': Category.objects.get(title=category),
        'content': content,
    }
    return context


def task_delete(request, queryset):
    checked_list = request.POST.getlist("checked_box")
    valid_ids = [todo_id for todo_id in checked_list if todo_id.isdigit()]
    deleted_count, _ = queryset.filter(pk__in=valid_ids).delete()
    if not deleted_count:
        messages.error(request, "Напоминание не найдено!")


def request_GET(request, todos, group_title: Optional[str] = None):
    categories = Category.objects.all()
    student = Student.objects.for_user(request.user)
    if not student:
        return redirect('home')
    group = student.groups
    context = {
        "todos": todos.order_by('due_date'),
        "categories": categories,
        'text_todo': group.title
    }
    if group_title:
        context['group_title'] = group_title
        context['text_todo'] = 'личные'

    return render(request, "todolist/index.html", context)
