import os

import django
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")


def pytest_configure():
    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
    settings.CELERY_ALWAYS_EAGER = True
    settings.CELERY_TASK_ALWAYS_EAGER = True
