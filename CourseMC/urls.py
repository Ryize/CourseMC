from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .rich_text import rich_text_image_upload
from .views import health_check, page_not_found_view, readiness_check

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('ready/', readiness_check, name='readiness_check'),
    path('coursemc_control/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path(
        'editor/upload/',
        rich_text_image_upload,
        name='rich_text_image_upload',
    ),
    path('api/v1/', include('api.urls')),
    path('', include('social_django.urls')),
    path('', include('Course.urls')),
    path('reviews/', include('reviews.urls')),
    path('questionnaire/', include('questionnaire.urls')),
    path('blog/', include('blog.urls')),
    path('interpreter/', include('py_interpreter.urls')),
    # path('chatgpt/', include('chatgpt.urls')),
    path('billing/', include('billing.urls')),
    path('todo/', include('todolist.urls')),
    path('certificate/', include('certificate.urls')),
    path('interview/', include('interview.urls')),
    path('code-review/', include('codereview.urls')),
    path('<path:url>/', page_not_found_view),
]

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns.append( path('<path:url>', page_not_found_view))
