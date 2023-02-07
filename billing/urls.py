from django.urls import path

from .views import *

urlpatterns = [
    path("", BillingView.as_view(), name="billing_index"),
    path("success/", BillingView.as_view(), name="billing_success"),
    path("fail/", BillingView.as_view(), name="billing_fail"),
]
