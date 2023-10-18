from django.urls import path

from certificate.views import *

urlpatterns = [
    path('generate/', generate, name='certificate_generate'),
    path('verify/', verify, name='certificate_verify'),
]
