from ckeditor_uploader.views import upload, browse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.urls import re_path
from django.views.decorators.cache import never_cache

urlpatterns = [
    re_path(r"^upload/", login_required(upload), name="ckeditor_upload"),
    re_path(
        r"^browse/",
        never_cache(staff_member_required(browse)),
        name="ckeditor_browse",
    ),
]
