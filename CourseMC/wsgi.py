"""
WSGI config for CourseMC project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CourseMC.settings")

application = get_wsgi_application()

# Модели уже загружены, поэтому фоновая проверка не обращается к базе во время
# инициализации приложений Django.
from billing.check_billing import start_payment_checker

start_payment_checker()
