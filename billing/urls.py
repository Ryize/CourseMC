from django.urls import path

from .views import *

urlpatterns = [
    path("", BillingView.as_view(), name="billing_index"),
    # path("check_billing/", check_billing, name="check_billing"),
    path("success/", billing_success, name="billing_success"),
    path("fail/", billing_success, name="billing_fail"),
]
