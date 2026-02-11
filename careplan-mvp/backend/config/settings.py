import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'dev-secret-key-change-in-production'
DEBUG = os.getenv('DEBUG', '0') == '1'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'corsheaders',
    'careplan',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://careplan:careplan123@localhost:5432/careplan')
db_parts = DATABASE_URL.replace('postgresql://', '').split('@')
user_pass = db_parts[0].split(':')
host_db = db_parts[1].split('/')
host_port = host_db[0].split(':')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': host_db[1],
        'USER': user_pass[0],
        'PASSWORD': user_pass[1],
        'HOST': host_port[0],
        'PORT': host_port[1] if len(host_port) > 1 else '5432',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS
CORS_ALLOW_ALL_ORIGINS = True

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
}

# OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
# 任务执行超时：10 分钟
CELERY_TASK_SOFT_TIME_LIMIT = 600
