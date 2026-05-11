import os
from pathlib import Path

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# ─────────────────────────────────────────────
# Приложения
# ─────────────────────────────────────────────
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Сторонние
    "django_filters",
    "django_tables2",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "two_factor",
    "auditlog",
    "import_export",
    "django_celery_beat",
    "widget_tweaks",
    # Приложения проекта
    "apps.accounts",
    "apps.dashboard",
    "apps.counterparties",
    "apps.directories",
    "apps.documents",
    "apps.registers",
    "apps.analytics",
    "apps.payments",
    "apps.reconciliation",
    "apps.reports",
    "apps.data_import",
    "apps.notifications",
    "apps.api"
]


# ─────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "apps.accounts.middleware.ActivityLogMiddleware",
    "apps.accounts.middleware.ActivityLogMiddleware",
    "apps.api.middleware.APITokenAuthMiddleware"
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ─────────────────────────────────────────────
# База данных
# ─────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "konckorm_db"),
        "USER": os.environ.get("DB_USER", "konckorm"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─────────────────────────────────────────────
# Пользовательская модель
# ─────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ─────────────────────────────────────────────
# Пароли
# ─────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# ─────────────────────────────────────────────
# Кэширование (Redis)
# ─────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 28800  # 8 часов
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True

# ─────────────────────────────────────────────
# Celery
# ─────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Europe/Moscow"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 1800
CELERY_TASK_SOFT_TIME_LIMIT = 1500

CELERY_BEAT_SCHEDULE = {
    "recalculate-analytics-daily": {
        "task": "apps.analytics.tasks.recalculate_all_kpi",
        "schedule": crontab(hour=2, minute=0),
    },
    "update-debt-register-daily": {
        "task": "apps.registers.tasks.update_debt_by_terms",
        "schedule": crontab(hour=2, minute=30),
    },
    "update-procurement-monthly": {
        "task": "apps.registers.tasks.update_procurement_volumes",
        "schedule": crontab(hour=3, minute=0, day_of_month=1),
    },
    "check-cash-gaps": {
        "task": "apps.payments.tasks.check_cash_gaps",
        "schedule": crontab(hour=8, minute=0, day_of_week="1-5"),
    },
    "send-overdue-notifications": {
        "task": "apps.notifications.tasks.send_overdue_alerts",
        "schedule": crontab(hour=9, minute=0, day_of_week="1-5"),
    },
}

# ─────────────────────────────────────────────
# Шаблоны
# ─────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.notifications.context_processors.unread_notifications_count",
            ],
        },
    },
]

# ─────────────────────────────────────────────
# Статика и медиа
# ─────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ─────────────────────────────────────────────
# Локализация
# ─────────────────────────────────────────────
LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

DATE_FORMAT = "d.m.Y"
DATETIME_FORMAT = "d.m.Y H:i"
SHORT_DATE_FORMAT = "d.m.Y"
DATE_INPUT_FORMATS = ["%d.%m.%Y", "%Y-%m-%d"]

# ─────────────────────────────────────────────
# Безопасность
# ─────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ─────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.yandex.ru")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 465))
EMAIL_USE_SSL = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@konckorm.ru")

# ─────────────────────────────────────────────
# Логирование
# ─────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "WARNING",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {"handlers": ["file", "console"], "level": "WARNING"},
        "apps": {"handlers": ["file", "console"], "level": "INFO"},
        "celery": {"handlers": ["file", "console"], "level": "INFO"},
    },
}

# ─────────────────────────────────────────────
# django-tables2
# ─────────────────────────────────────────────
DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap5.html"

# ─────────────────────────────────────────────
# django-auditlog
# ─────────────────────────────────────────────
AUDITLOG_INCLUDE_ALL_MODELS = True

# ─────────────────────────────────────────────
# Настройки проекта (кастомные)
# ─────────────────────────────────────────────
KPI_THRESHOLDS = {
    "overdue_ratio": {
        "green": 0.05,
        "yellow": 0.15,
    },
    "turnover_days": {
        "green": 30,
        "yellow": 60,
    },
}

OVERDUE_INTERVALS = [
    (0, 30, "до 30 дней"),
    (30, 60, "30–60 дней"),
    (60, 90, "60–90 дней"),
    (90, None, "свыше 90 дней"),
]

UPCOMING_PAYMENT_WARNING_DAYS = 3
PAYMENT_CALENDAR_DEFAULT_HORIZON = 30
KEY_SUPPLIER_THRESHOLD = 0.80
