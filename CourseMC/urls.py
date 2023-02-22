from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import page_not_found_view

urlpatterns = [
    path("coursemc_control/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("ckeditor/", include("CourseMC.ckeditor_urls")),
    path("api/v1/", include("api.urls")),
    path("", include("social_django.urls")),
    path("", include("Course.urls")),
    path("reviews/", include("reviews.urls")),
    path("questionnaire/", include("questionnaire.urls")),
    path("blog/", include("blog.urls")),
    path('interpreter/', include("py_interpreter.urls")),
    path('chatgpt/', include("chatgpt.urls")),
    path("billing/", include("billing.urls")),
    path("todo/", include("todolist.urls")),
    path("<path:url>/", page_not_found_view),
]

from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns.append( path("<path:url>", page_not_found_view))
