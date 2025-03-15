import os
import dj_database_url
from dotenv import load_dotenv
from pathlib import Path

# ✅ Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = os.path.join(BASE_DIR, ".env")  
load_dotenv(ENV_PATH)  

# ✅ Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgres://postgres:Meme2025###@127.0.0.1:5432/apexfin-database"

DATABASES = {
    "default": dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
}

# ✅ Security Keys
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "fallback-secret-key")
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = ['127.0.0.1', 'apexfin-holy-leaf-5090.fly.dev']

CSRF_TRUSTED_ORIGINS = ["https://apexfin-holy-leaf-5090.fly.dev"]

# ✅ Login & Logout Redirects
LOGIN_REDIRECT_URL = "/users/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# ✅ Application Definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "users",
]

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
        "DIRS": [os.path.join(BASE_DIR, "templates")],  # Allow all templates
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

# ✅ Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ✅ Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ✅ Static Files
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]  # Ensure static folder exists

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ✅ USDT Wallet Configuration
USDT_WALLET_ADDRESS = os.getenv("USDT_WALLET_ADDRESS", "TK9MzgkdryfdVJy6UfHeU6mv1yhESnbKYT")
USDT_WALLET_QR = os.getenv("USDT_WALLET_QR", "YOUR_QR_IMAGE_URL_HERE")

# ✅ TronScan API for USDT Payment Verification
TRONSCAN_API_KEY = os.getenv("TRONSCAN_API_KEY", "2aacf7c1-3e21-4856-91bc-18a8362d64dc")
TRONSCAN_API_URL = "https://apilist.tronscanapi.com/api/transaction-info"

# ✅ Debugging
print("DEBUG:", DEBUG)
print("Allowed Hosts:", ALLOWED_HOSTS)
