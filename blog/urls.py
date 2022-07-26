from django.urls import path

from .views import *

urlpatterns = [
    path('', PostListView.as_view(), name='blog_home'),
    path('post/<int:pk>', PostView.as_view(), name='post_view'),
    path('create_post/', PostCreateView.as_view(), name='create_post'),
    path('my_post/', MyPostListView.as_view(), name='my_post'),
    path('create_comment/', create_comment, name='create_comment'),
]
