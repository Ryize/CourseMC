"""CourseMC URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
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
]

#handler404 = "CourseMC.views.page_not_found_view"

from django.contrib.staticfiles.urls import staticfiles_urlpatterns

# ... остальная часть вашего URLconf здесь ...

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)