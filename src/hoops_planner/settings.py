"""Minimal Django settings for testing."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# DEBUG defaults to True so `manage.py runserver` and the test suite work
# without any configuration. Set DEBUG=False in production (e.g. via the
# environment) — this also enables the security hardening below.
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# Fail fast in production rather than running with an insecure default key.
_secret_key = os.getenv("SECRET_KEY", "")
if _secret_key:
    SECRET_KEY = _secret_key
elif DEBUG:
    SECRET_KEY = "insecure-dev-key"
else:
    raise RuntimeError(
        "SECRET_KEY must be set when DEBUG is False. "
        "Generate one with: python -c 'from django.core.management.utils "
        "import get_random_secret_key; print(get_random_secret_key())'"
    )

if DEBUG:
    ALLOWED_HOSTS: list[str] = ["*"]
else:
    # In production, restrict allowed hosts to the site origin. Set
    # SITE_URL to a comma-separated list for multiple domains.
    _site = os.getenv("SITE_URL", "")
    _hosts = (_site.replace("https://", "").replace("http://", "")).split(",")
    ALLOWED_HOSTS = [h for h in _hosts if h]
    if not ALLOWED_HOSTS:
        raise RuntimeError(
            "SITE_URL must be set when DEBUG is False so ALLOWED_HOSTS can be derived. "
            "Example: SITE_URL=https://hoops.bcvido.nl"
        )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "hoops_planner.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "hoops_planner.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Database configuration — supports both SQLite (dev) and PostgreSQL (prod)
DB_ENGINE = os.getenv("DB_ENGINE", "")
if DB_ENGINE.startswith("postgresql"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "hoops_planner"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "db"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("DB_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"

# CORS settings for React frontend
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    os.getenv("SITE_URL", "http://localhost:5173"),
]
CORS_ALLOW_CREDENTIALS = True

# Site URL for password reset / email verification links
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173")

# Production hardening — active only when DEBUG=False
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "true").lower() == "true"
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Email backend (console for development, SMTP for production)
EMAIL_CONFIG = os.getenv("EMAIL_BACKEND", "").startswith(
    "django.core.mail.backends.smtp"
)
if EMAIL_CONFIG:
    EMAIL_BACKEND = os.getenv(
        "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
    )
    EMAIL_HOST = os.getenv("EMAIL_HOST", "")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "hoops-planner@localhost")

# REST framework settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    # Throttling is a production safeguard; disabled in dev/test so the e2e
    # suite (which registers many users) doesn't trip the anon rate limit.
    "DEFAULT_THROTTLE_CLASSES": [] if DEBUG else [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# DRF Spectacular settings
SPECTACULAR_SETTINGS = {
    "TITLE": "Hoops Planner API",
    "DESCRIPTION": "Planning app for basketball club tasks.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
