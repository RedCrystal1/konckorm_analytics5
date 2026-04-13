from .base import *  # noqa: F401, F403

DEBUG = True
SECRET_KEY = "django-insecure-dev-key-change-in-production-!!!"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Disable SSL in dev
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Use SQLite for quick local dev (override with env vars for PostgreSQL)
import os

if not os.environ.get("DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Use file-based sessions in dev if no Redis
if not os.environ.get("REDIS_URL"):
    SESSION_ENGINE = "django.contrib.sessions.backends.db"
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# Email to console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Debug toolbar
INSTALLED_APPS += [  # noqa: F405
    "debug_toolbar",
    "django_extensions",
]
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

# Отключаем 2FA middleware в dev-режиме
MIDDLEWARE = [m for m in MIDDLEWARE if 'OTP' not in m and 'otp' not in m]

# Явно отключаем SSL-редиректы
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# Админка без 2FA
LOGIN_URL = "/accounts/login/"

# Убираем ActivityLog middleware в dev
MIDDLEWARE = [m for m in MIDDLEWARE if "ActivityLog" not in m]

ALLOWED_HOSTS = ["*"]

# Админка использует свой собственный логин
ADMIN_LOGIN_URL = "/admin/login/"

# Убеждаемся что LOGIN_URL не перехватывает админку
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Полностью отключаем two_factor в dev (он переопределяет admin login)
INSTALLED_APPS = [a for a in INSTALLED_APPS if a not in ("two_factor", "django_otp", "django_otp.plugins.otp_totp")]
MIDDLEWARE = [m for m in MIDDLEWARE if "otp" not in m.lower() and "two_factor" not in m.lower() and "ActivityLog" not in m]