from typing import Optional

from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
            task_delete(request, TodoListUser)
        return redirect("todo")
    todos = TodoListUser.objects.filter(user=request.user).all()
    return request_GET(request, todos)


@login_required
def todo_group(request):
    group = Student.objects.filter(name=request.user.username).first().groups
    if request.method == "POST":
        if "task_add" in request.POST:
            if not valid_params(request):
                return redirect("todo")
            TodoListGroup.objects.create(**get_request_data(request),
                                         group=group,
                                         )
        if "task_delete" in request.POST:
            task_delete(request, TodoListGroup)
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


def task_delete(request, model):
    checked_list = request.POST.get("checked_box", [])
    for todo_id in checked_list:
        todo = model.objects.filter(pk=int(todo_id)).first()
        if not todo:
            messages.error(request, "Напоминание не найдено!")
        todo.delete()


def request_GET(request, todos, group_title: Optional[str] = None):
    categories = Category.objects.all()
    student = Student.objects.filter(name=request.user.username).first()
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
