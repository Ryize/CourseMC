from django.urls import path

from reviews.views import *


urlpatterns = [
    path('', ReviewView.as_view(), name='review'),
    path('check_left_review/', check_left_review, name='check_left_review'),
]
