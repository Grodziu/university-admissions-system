"""Local desktop deployment. The client never receives database credentials."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get('PK_DATA_DIR', BASE_DIR / 'runtime'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SECRET_KEY = os.environ.get('PK_SECRET_KEY', 'development-only-run-through-launcher')
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver'] + os.environ.get('PK_SERVER_HOSTS', '').split(',')
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes',
                  'rest_framework', 'admissions']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware']
ROOT_URLCONF = 'server.urls'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'admissions.User'
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.environ.get('PK_DB_NAME', 'rekrutacja'),
    'USER': os.environ.get('PK_DB_USER', 'pk_app'),
    'PASSWORD': os.environ.get('PK_DB_PASSWORD', ''),
    'HOST': '127.0.0.1', 'PORT': os.environ.get('PK_DB_PORT', '55432'),
    'CONN_MAX_AGE': 60,
}}
USE_TZ = True
TIME_ZONE = 'Europe/Warsaw'
LANGUAGE_CODE = 'pl'
MEDIA_ROOT = Path(os.environ.get('PK_DOCUMENTS_PATH', DATA_DIR / 'documents'))
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024 * 1024
EMAIL_HOST = os.environ.get('PK_SMTP_HOST', '')
DEFAULT_FROM_EMAIL = os.environ.get('PK_SMTP_FROM', '')
EMAIL_HOST_USER = os.environ.get('PK_SMTP_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('PK_SMTP_PASSWORD', '')
smtp_security = os.environ.get('PK_SMTP_SECURITY', 'starttls')
EMAIL_USE_TLS = smtp_security == 'starttls'
EMAIL_USE_SSL = smtp_security == 'ssl'
EMAIL_PORT = int(os.environ.get('PK_SMTP_PORT', '465' if EMAIL_USE_SSL else '587'))
EMAIL_TIMEOUT = 12
PK_MAIL_ENABLED = bool(EMAIL_HOST and DEFAULT_FROM_EMAIL)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['admissions.auth.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'EXCEPTION_HANDLER': 'admissions.api.exception_handler',
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '200/min', 'login': '20/min'},
    'UNAUTHENTICATED_USER': None,
}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
