from django.urls import path

from .views import *

urlpatterns = [
    path("", BillingView.as_view(), name="billing_index"),
]
