import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
APP_ENV = os.getenv("APP_ENV", "test")
if APP_ENV not in {"test", "production"}:
    raise ImproperlyConfigured("APP_ENV must be test or production")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def database_config():
    value = os.getenv("DATABASE_URL")
    if not value:
        if APP_ENV == "production":
            raise ImproperlyConfigured("DATABASE_URL is required in production")
        # ponytail: SQLite serializes local writes; PostgreSQL handles concurrent production jobs.
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": os.getenv("SQLITE_PATH", BASE_DIR / "db.sqlite3"), "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"}}
    parsed = urlparse(value)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use PostgreSQL")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname,
        "PORT": parsed.port or 5432,
        "CONN_MAX_AGE": 60,
    }


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "test-only-secret-key")
if APP_ENV == "production" and SECRET_KEY == "test-only-secret-key":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production")

DEBUG = env_bool("DJANGO_DEBUG", APP_ENV == "test")
ALLOWED_HOSTS = [value.strip() for value in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if value.strip()]
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "accounts",
    "catalog",
    "projects",
    "processing",
    "commerce",
    "operations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "momenria.middleware.SessionLifetimeMiddleware",
    "momenria.middleware.PublicAccessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "momenria.middleware.SecurityHeadersMiddleware",
    "momenria.middleware.RequestIdMiddleware",
    "momenria.middleware.OperatorMfaMiddleware",
]

ROOT_URLCONF = "momenria.urls"
WSGI_APPLICATION = "momenria.wsgi.application"
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["allauth.account.auth_backends.AuthenticationBackend"]

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "accounts.context_processors.authentication_return",
    ]},
}]

DATABASES = {"default": database_config()}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "Asia/Jakarta"
LANGUAGE_CODE = "id"
LANGUAGES = [("id", "Bahasa Indonesia")]
USE_I18N = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = Path(os.getenv("PRIVATE_MEDIA_ROOT", BASE_DIR / "private-media"))
MEDIA_URL = "/private-media-not-public/"
TOMBSTONE_ROOT = Path(os.getenv("TOMBSTONE_ROOT", MEDIA_ROOT / "tombstones"))
FILE_UPLOAD_HANDLERS = ["django.core.files.uploadhandler.TemporaryFileUploadHandler"]
FILE_UPLOAD_MAX_MEMORY_SIZE = 0
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("REQUEST_MAX_BYTES", str(1024 * 1024)))

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = APP_ENV == "production"
CSRF_COOKIE_SECURE = APP_ENV == "production"
CSRF_TRUSTED_ORIGINS = [APP_BASE_URL] if APP_BASE_URL.startswith("https://") else []
CSRF_FAILURE_VIEW = "momenria.http.csrf_failure"
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_ABSOLUTE_AGE = 30 * 24 * 60 * 60
OPERATOR_SESSION_IDLE_SECONDS = 60 * 60
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = APP_ENV == "production"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
TRUSTED_PROXY_HOST = os.getenv("TRUSTED_PROXY_HOST", "").strip()
SECURE_HSTS_SECONDS = 31536000 if APP_ENV == "production" else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = APP_ENV == "production"
SECURE_HSTS_PRELOAD = APP_ENV == "production"

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[MomenRia] "
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_RATE_LIMITS = {"login_failed": "5/5m", "signup": "5/h", "reset_password": "5/h"}
ACCOUNT_REAUTHENTICATION_TIMEOUT = 5 * 60
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
PUBLIC_ACCESS = env_bool("PUBLIC_ACCESS", False)
PUBLIC_OWNER_EMAIL = os.getenv("PUBLIC_OWNER_EMAIL", "public@momenria.invalid")
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("SMTP_HOST", "")
EMAIL_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.getenv("SMTP_USERNAME", "")
EMAIL_HOST_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv("SMTP_FROM", "MomenRia <no-reply@localhost>")

UPLOAD_MAX_BYTES = int(os.getenv("UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
UPLOAD_MAX_PIXELS = int(os.getenv("UPLOAD_MAX_PIXELS", "40000000"))
SOURCE_RETENTION_DAYS = int(os.getenv("SOURCE_RETENTION_DAYS", "7"))
RESULT_RETENTION_DAYS = int(os.getenv("RESULT_RETENTION_DAYS", "30"))
BUSINESS_NAME = "MomenRia"
SUPPORT_EMAIL = "support@momenria.id"
SUPPORT_PHONE = "+6282226669926"
TERMS_VERSION = "2026-10-10"
REFUND_POLICY_VERSION = "2026-10-10"
ADMISSION_ENABLED = env_bool("ADMISSION_ENABLED", False)
DAILY_BUDGET_IDR = int(os.getenv("DAILY_BUDGET_IDR", "0"))
ALLOW_UNBOUNDED_TEST_BUDGET = env_bool("ALLOW_UNBOUNDED_TEST_BUDGET", False)
AI_MAX_CONCURRENCY = int(os.getenv("AI_MAX_CONCURRENCY", "1"))
AI_MAX_SAFE_RETRIES = int(os.getenv("AI_MAX_SAFE_RETRIES", "1"))
JOB_QUEUE_LIMIT = int(os.getenv("JOB_QUEUE_LIMIT", "20"))
STORAGE_MIN_FREE_BYTES = int(os.getenv("STORAGE_MIN_FREE_BYTES", str(20 * 1024 * 1024 * 1024)))
STORAGE_MAX_USED_PERCENT = int(os.getenv("STORAGE_MAX_USED_PERCENT", "85"))
AI_CONNECT_TIMEOUT_SECONDS = int(os.getenv("AI_CONNECT_TIMEOUT_SECONDS", "10"))
AI_REQUEST_TIMEOUT_SECONDS = int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "180"))
AI_UPSCALE_MIN_LONG_EDGE = int(os.getenv("AI_UPSCALE_MIN_LONG_EDGE", "1400"))
NINE_ROUTER_BASE_URL = os.getenv("NINE_ROUTER_BASE_URL", "")
NINE_ROUTER_API_KEY = os.getenv("NINE_ROUTER_API_KEY", "")
NINE_ROUTER_GENERATION_MODEL = os.getenv("NINE_ROUTER_GENERATION_MODEL", "image-generation")
NINE_ROUTER_GENERATION_PATH = os.getenv("NINE_ROUTER_GENERATION_PATH", "")
NINE_ROUTER_EDIT_MODEL = os.getenv("NINE_ROUTER_EDIT_MODEL", "")
NINE_ROUTER_EDIT_PATH = os.getenv("NINE_ROUTER_EDIT_PATH", "")
AI_GATEWAY_MODE = os.getenv("AI_GATEWAY_MODE", "disabled")
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "disabled")
PAYMENT_ENV = os.getenv("PAYMENT_ENV", "sandbox")
PAYMENT_SERVER_KEY = os.getenv("PAYMENT_SERVER_KEY", "")
RESULT_FONT_PATH = os.getenv("RESULT_FONT_PATH", "")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
BACKUP_MARKER_PATH = Path(os.getenv("BACKUP_MARKER_PATH", "/data/tombstones/last-successful-backup"))
FACE_DETECTOR_MODEL = Path(os.getenv("FACE_DETECTOR_MODEL", BASE_DIR / "models/yunet/face_detection_yunet_2023mar.onnx"))
FACE_CONFIDENCE_THRESHOLD = float(os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.8"))
FACE_MIN_SIZE_PX = int(os.getenv("FACE_MIN_SIZE_PX", "120"))
FACE_BLUR_THRESHOLD = float(os.getenv("FACE_BLUR_THRESHOLD", "60"))
FACE_MIN_BRIGHTNESS = float(os.getenv("FACE_MIN_BRIGHTNESS", "45"))
FACE_MAX_BRIGHTNESS = float(os.getenv("FACE_MAX_BRIGHTNESS", "215"))

if APP_ENV == "production":
    if PUBLIC_ACCESS:
        raise ImproperlyConfigured("Production requires PUBLIC_ACCESS=false to isolate customer photos")
    if ALLOW_UNBOUNDED_TEST_BUDGET:
        raise ImproperlyConfigured("Production rejects unbounded test budget")
    if DEBUG or not APP_BASE_URL.startswith("https://") or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("Production requires DEBUG=false, HTTPS base URL, and explicit hosts")
    if PAYMENT_ENV != "production" and PAYMENT_PROVIDER != "disabled":
        raise ImproperlyConfigured("Production rejects sandbox payment configuration")
    if AI_GATEWAY_MODE == "fake":
        raise ImproperlyConfigured("Production rejects fake AI gateway")
    if PAYMENT_PROVIDER == "fake":
        raise ImproperlyConfigured("Production rejects fake payment provider")
    if "nadzeriserver" in NINE_ROUTER_BASE_URL:
        raise ImproperlyConfigured("Production rejects test 9Router endpoint")
    if AI_GATEWAY_MODE != "disabled" and not all((NINE_ROUTER_BASE_URL, NINE_ROUTER_API_KEY, NINE_ROUTER_GENERATION_PATH)):
        raise ImproperlyConfigured("Enabled production AI requires base URL, API key, and generation path")
    if PAYMENT_PROVIDER == "midtrans" and not PAYMENT_SERVER_KEY:
        raise ImproperlyConfigured("Enabled production payment requires server key")
    if EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend" or not all((EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)):
        raise ImproperlyConfigured("Production email verification requires SMTP credentials")
    if TOMBSTONE_ROOT == MEDIA_ROOT or MEDIA_ROOT in TOMBSTONE_ROOT.parents:
        raise ImproperlyConfigured("Production tombstone journal must use a separate restore boundary")
    if ADMISSION_ENABLED and not all((ALERT_EMAIL, str(BACKUP_MARKER_PATH))):
        raise ImproperlyConfigured("Enabled production admission requires alert and backup monitoring configuration")
elif PAYMENT_ENV == "production":
    raise ImproperlyConfigured("Test rejects live payment configuration")

if AI_GATEWAY_MODE not in {"disabled", "fake", "9router"} or PAYMENT_PROVIDER not in {"disabled", "fake", "midtrans"}:
    raise ImproperlyConfigured("Unsupported AI or payment provider mode")
if AI_MAX_CONCURRENCY < 1 or AI_MAX_SAFE_RETRIES not in {0, 1} or JOB_QUEUE_LIMIT < 1 or not 1024 <= AI_UPSCALE_MIN_LONG_EDGE < 2048:
    raise ImproperlyConfigured("Invalid processing bounds")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s %(message)s"}},
    "filters": {"request_id": {"()": "momenria.logging.RequestIdFilter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard", "filters": ["request_id"]}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
