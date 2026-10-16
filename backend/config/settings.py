"""EQura Django settings.

Configuration comes from environment variables (see `.env.example`). Production-unsafe
defaults are only used when DJANGO_DEBUG=true.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG is off.")
    SECRET_KEY = "dev-only-insecure-secret-key"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    # Domain modules (each owns its tables and business rules).
    "apps.identity",
    "apps.audit",
    "apps.outbox",
    "apps.profiles",
    "apps.trust_safety",
    "apps.social",
    "apps.opportunities",
    "apps.messaging",
    "apps.notifications",
]

MIDDLEWARE = [
    "shared.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "equra"),
        "USER": env("POSTGRES_USER", "equra"),
        "PASSWORD": env("POSTGRES_PASSWORD", "equra"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(env("POSTGRES_CONN_MAX_AGE", "60")),
        "OPTIONS": {"sslmode": env("POSTGRES_SSLMODE", "prefer")},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "identity.User"

REDIS_URL = env("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Sessions, cookies, CSRF -------------------------------------------------
# Browser-first auth: server-side sessions in HttpOnly cookies (docs/api-and-security.md §3).
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = int(timedelta(days=14).total_seconds())
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
# The SPA reads the CSRF cookie and echoes it in X-CSRFToken, so it must not be HttpOnly.
CSRF_COOKIE_HTTPONLY = False

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

# --- Email -------------------------------------------------------------------
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@equra.local")
PASSWORD_RESET_TIMEOUT = int(timedelta(hours=1).total_seconds())

# --- REST framework ----------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["shared.auth.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "shared.pagination.CreatedAtCursorPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "shared.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", "120/min"),
        "user": env("THROTTLE_USER", "600/min"),
        "auth": env("THROTTLE_AUTH", "10/min"),
        "password_reset": env("THROTTLE_PASSWORD_RESET", "5/hour"),
        "applications": env("THROTTLE_APPLICATIONS", "30/hour"),
        "listings": env("THROTTLE_LISTINGS", "60/hour"),
        "posts": env("THROTTLE_POSTS", "30/hour"),
        "comments": env("THROTTLE_COMMENTS", "60/hour"),
        "social": env("THROTTLE_SOCIAL", "120/min"),
        "messages": env("THROTTLE_MESSAGES", "60/min"),
        "conversations": env("THROTTLE_CONVERSATIONS", "30/hour"),
        "reports": env("THROTTLE_REPORTS", "20/hour"),
    },
}
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append("rest_framework.renderers.BrowsableAPIRenderer")

EXPOSE_API_DOCS = env_bool("EXPOSE_API_DOCS", DEBUG)
SPECTACULAR_SETTINGS = {
    "TITLE": "EQura API",
    "DESCRIPTION": "Artist network and gig marketplace API (v1).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Stable, readable enum names for generated frontend types.
    "ENUM_NAME_OVERRIDES": {
        "ApplicationStatus": "apps.opportunities.models.Application.Status",
        "OpportunityStatus": "apps.opportunities.models.Opportunity.Status",
        "EventStatus": "apps.opportunities.models.Event.Status",
        "BookingStatus": "apps.opportunities.models.Booking.Status",
        "ReportStatus": "apps.trust_safety.models.Report.Status",
        "AccountStatus": "apps.identity.models.AccountStatus",
        "SelfServiceRole": ["artist", "organizer"],
    },
}

# --- Outbox / background work -----------------------------------------------
# "inline": dispatch outbox events in-process after commit (local dev, no worker needed).
# "celery": enqueue a Celery task after commit; a beat sweep retries anything missed.
# "manual": never dispatch automatically (tests call process_pending() explicitly).
OUTBOX_DISPATCH = env("OUTBOX_DISPATCH", "inline")
OUTBOX_MAX_ATTEMPTS = int(env("OUTBOX_MAX_ATTEMPTS", "10"))

CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 60
CELERY_BEAT_SCHEDULE = {
    "outbox-sweep": {"task": "apps.outbox.tasks.dispatch_outbox", "schedule": 30.0},
}

# --- Logging -----------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "shared.middleware.RequestIdLogFilter"}},
    "formatters": {
        "structured": {
            "format": "%(asctime)s level=%(levelname)s logger=%(name)s "
            "request_id=%(request_id)s msg=%(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "filters": ["request_id"],
        }
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
