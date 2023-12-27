from django.urls import path

from certificate.views import *

urlpatterns = [
    path('generate/', generate, name='certificate_generate'),
    path('verify/', verify, name='certificate_verify'),
    path('download/<int:number>/', download, name='certificate_download'),
]
