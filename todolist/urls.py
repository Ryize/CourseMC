from django.urls import path

from todolist.views import todo_user, todo_group

urlpatterns = [
    path('', todo_user, name="todo"),
    path('group/', todo_group, name="todo_group"),
]
