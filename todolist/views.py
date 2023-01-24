from django.shortcuts import render, redirect
from .models import TodoList, Category


def index(request):
    if request.method == "POST":
        if "task_add" in request.POST:
            title = request.POST.get('description')
            date = str(request.POST.get('date'))
            category = request.POST.get('category_select')
            if not (title and date and category):
                return redirect("todo")
            content = title + " -- " + date + " " + category
            TodoList.objects.create(title=title, content=content, due_date=date,
                                    category=Category.objects.get(title=category),
                                    user=request.user,
                                    )
            return redirect("todo")

        if "task_delete" in request.POST:
            checked_list = request.POST.get("checked_box", [])
            for todo_id in checked_list:
                todo = TodoList.objects.get(id=int(todo_id))
                todo.delete()
    todos = TodoList.objects.filter(user=request.user).all()
    categories = Category.objects.all()
    return render(request, "index.html", {"todos": todos, "categories": categories})
