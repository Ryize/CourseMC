from django.urls import path

from todolist.views import index

urlpatterns = [
    path('', index, name="todo"),
]
