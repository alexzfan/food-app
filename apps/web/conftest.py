import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_TESTING", "1")

import django
django.setup()

from django.conf import settings
if settings.configured:
    settings.STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"
