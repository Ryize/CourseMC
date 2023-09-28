from django.urls import path

from .views import *

urlpatterns = [
    path('', BillingView.as_view(), name='billing_index'),
    path('success/', billing_success, name='billing_success'),
    path('fail/', billing_success, name='billing_fail'),
]
