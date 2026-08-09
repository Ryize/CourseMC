from django.urls import path

from .views import *

urlpatterns = [
    path("send_review/", send_review, name="review_send"),
    path("list/", list_review, name="review_list"),
    path("review/<int:pk>/", my_review, name="review_my"),
]
