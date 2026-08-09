# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, "/var/www/u1450880/data/www/coursemc.space/CourseMC")
sys.path.insert(1, "/var/www/u1450880/data/djangoenv/lib/python3.7/site-packages")
os.environ["DJANGO_SETTINGS_MODULE"] = "Course.settings"
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
