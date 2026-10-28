import os
from pathlib import Path
import dj_database_url
B=Path(__file__).resolve().parent.parent
E=os.environ.get
DEBUG=E('DEBUG','0')=='1'
SECRET_KEY=E('SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG: raise RuntimeError('SECRET_KEY is required when DEBUG=0')
    SECRET_KEY='dev-only-insecure-key'
ALLOWED_HOSTS=[h.strip() for h in E('ALLOWED_HOSTS','localhost,127.0.0.1').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS=[o.strip() for o in E('CSRF_TRUSTED_ORIGINS','http://localhost:5173,http://127.0.0.1:5173' if DEBUG else '').split(',') if o.strip()]
RENDER_EXTERNAL_HOSTNAME=E('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','rest_framework','core']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','core.middleware.CSPMiddleware','core.middleware.HealthMiddleware']
ROOT_URLCONF='bantay.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[B/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','core.context.site','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='bantay.wsgi.application'
DATABASES={'default':dj_database_url.config(default=f'sqlite:///{B/"db.sqlite3"}',conn_max_age=600,conn_health_checks=True)}
if E('DB_SSL')=='1' and DATABASES['default']['ENGINE'].endswith('postgresql'): DATABASES['default'].setdefault('OPTIONS',{})['sslmode']='require'
CACHES={'default':{'BACKEND':'django.core.cache.backends.db.DatabaseCache','LOCATION':'bb_cache'}}
AUTH_USER_MODEL='core.User'
PASSWORD_HASHERS=['django.contrib.auth.hashers.Argon2PasswordHasher','django.contrib.auth.hashers.PBKDF2PasswordHasher']
AUTH_PASSWORD_VALIDATORS=[{'NAME':f'django.contrib.auth.password_validation.{n}'} for n in ('UserAttributeSimilarityValidator','MinimumLengthValidator','CommonPasswordValidator','NumericPasswordValidator')]
SESSION_COOKIE_AGE=1800; SESSION_SAVE_EVERY_REQUEST=True  # BR-07: 30 min inactivity
SESSION_COOKIE_HTTPONLY=True; SESSION_COOKIE_SAMESITE='Lax'
SESSION_COOKIE_SECURE=CSRF_COOKIE_SECURE=not DEBUG
SECURE_SSL_REDIRECT=not DEBUG and E('SSL_REDIRECT','1')=='1'
SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
SECURE_HSTS_SECONDS=0 if DEBUG else 31536000; SECURE_HSTS_INCLUDE_SUBDOMAINS=not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF=True; SECURE_REFERRER_POLICY='same-origin'; X_FRAME_OPTIONS='DENY'
REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'],'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],'DEFAULT_RENDERER_CLASSES':['rest_framework.renderers.JSONRenderer'],
 'DEFAULT_THROTTLE_CLASSES':['rest_framework.throttling.AnonRateThrottle','rest_framework.throttling.UserRateThrottle','rest_framework.throttling.ScopedRateThrottle'],'DEFAULT_THROTTLE_RATES':{'anon':'60/min','user':'300/min','auth':'10/min'}}
LANGUAGE_CODE='en'; TIME_ZONE='Asia/Manila'; USE_TZ=True
STATIC_URL='/static/'; STATIC_ROOT=B/'staticfiles'
STATICFILES_DIRS=[B/'static']
STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'whitenoise.storage.CompressedStaticFilesStorage'}}
LOGIN_URL='/login/'
MEDIA_ROOT=Path(E('MEDIA_ROOT',str(B/'media')))
DATA_UPLOAD_MAX_MEMORY_SIZE=16*1024*1024
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend' if E('EMAIL_HOST') else 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST=E('EMAIL_HOST',''); EMAIL_PORT=int(E('EMAIL_PORT','587')); EMAIL_USE_TLS=True
EMAIL_HOST_USER=E('EMAIL_HOST_USER',''); EMAIL_HOST_PASSWORD=E('EMAIL_HOST_PASSWORD','')
DEFAULT_FROM_EMAIL=E('DEFAULT_FROM_EMAIL','BantayBarangay <no-reply@localhost>')
LOGGING={'version':1,'disable_existing_loggers':False,'handlers':{'c':{'class':'logging.StreamHandler'}},'root':{'handlers':['c'],'level':'INFO'}}