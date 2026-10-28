from django.contrib import admin
from django.contrib.auth import views as av
from django.urls import include,path
from core.views import csrf,healthz
urlpatterns=[path('django-admin/',admin.site.urls),path('healthz',healthz),path('api/auth/csrf/',csrf),path('api/',include('core.urls')),
 path('reset/<uidb64>/<token>/',av.PasswordResetConfirmView.as_view(),name='password_reset_confirm'),path('reset/done/',av.PasswordResetCompleteView.as_view(),name='password_reset_complete'),
 path('',include('core.web_urls'))]
