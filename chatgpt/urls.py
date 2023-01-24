from django.urls import path

from chatgpt.views import *

urlpatterns = [
    path('', index, name='gpt_home'),
    path('send_to_api/', send_request_api, name='send_request_api'),
]
