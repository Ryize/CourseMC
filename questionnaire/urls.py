from django.urls import path
from .views import *

urlpatterns = [
    path('', index, name='questionnaireIndex'),
    path('create_poll/', create_poll, name='create_poll'),
    path('create_question/<int:quiz_id>', create_question, name='create_question'),
    path('create_answer/', create_answer, name='create_answer'),
    path('my_polls/', QuizListView.as_view(), name='my_poll'),
    path('go_poll/', go_poll, name='go_poll'),
    path('take_poll/<int:poll_id>', take_poll, name='take_poll'),
    path('rating/<int:poll_id>', rating, name='rating'),
]
