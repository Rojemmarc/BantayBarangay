from django.urls import path
from rest_framework.routers import SimpleRouter
from . import views as v
R=SimpleRouter();R.register('reports',v.ReportViewSet,basename='report')
urlpatterns=[path('',v.api_root),path('auth/register/',v.register),path('auth/login/',v.login_view),path('auth/logout/',v.logout_view),path('auth/me/',v.me),path('auth/password-reset/',v.password_reset),
 path('barangays/',v.barangays),path('meta/',v.meta),path('stats/',v.stats),path('announcements/',v.announcements),path('announcements/<int:pk>/',v.announcement_delete),
 path('notifications/',v.notifications),path('ranking/',v.ranking),path('lgu/summary/',v.lgu_summary),path('photos/<int:pk>/',v.photo)]+R.urls
