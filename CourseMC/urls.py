from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('coursemc_control/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('api/v1/', include('api.urls')),
    path('', include('social_django.urls')),
    path('', include('Course.urls')),
    path('reviews/', include('reviews.urls')),
    path('questionnaire/', include('questionnaire.urls')),
    path('blog/', include('blog.urls')),
]

from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)
