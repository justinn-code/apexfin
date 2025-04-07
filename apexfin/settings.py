import os
import dj_database_url
from dotenv import load_dotenv
from pathlib import Path
import logging
from decouple import config, Csv
load_dotenv()

# ✅ Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

AUTH_USER_MODEL = "users.CustomUser"

# ✅ Security Settings
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "fallback-secret-key")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())
CSRF_TRUSTED_ORIGINS = ["https://apexfin-bam.fly.dev"]

# ✅ Secure Session Handling
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ✅ Database Configuration using DATABASE_URL from .env
DATABASES = {
    'default': dj_database_url.parse(config('DATABASE_URL'))
}
print("🌍 DATABASE_URL:", config('DATABASE_URL'))


# ✅ Login & Logout Redirects
LOGIN_REDIRECT_URL = "/users/dashboard/"
LOGOUT_REDIRECT_URL = "/"

## Add crispy forms to installed apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "users.apps.UsersConfig", 
    "crispy_forms",  # Add this
    "crispy_bootstrap5",  # Add this for Bootstrap 5
]

# Configure Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"  # Bootstrap 5
CRISPY_TEMPLATE_PACK = "bootstrap5"  # Use Bootstrap 5 for crispy forms

# ✅ Middleware Configuration
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "apexfin.urls"

# ✅ Template Configuration
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],  # Root templates directory
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

WSGI_APPLICATION = "apexfin.wsgi.application"

# ✅ Password Validators
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ✅ Localization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ✅ Static & Media Files Configuration
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

from decouple import config

IPSTACK_API_KEY = config('IPSTACK_API_KEY')


# ✅ USDT Wallet Configuration
USDT_WALLET_ADDRESS = os.getenv("USDT_WALLET_ADDRESS")
TRONSCAN_API_KEY = os.getenv("TRONSCAN_API_KEY")
TRONSCAN_API_URL = "https://api.tronscan.org/api/transaction-info"

# ✅ Logging Configuration
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOGS_DIR, "django.log"),
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}
