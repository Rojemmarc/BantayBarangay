from django.urls import path
from . import web as w
urlpatterns=[path('',w.index,name='index'),path('login/',w.login_view,name='login'),path('logout/',w.logout_view,name='logout'),path('register/',w.register_view,name='register'),
 path('forgot/',w.forgot,name='forgot'),path('legal/',w.legal,name='legal'),path('app/',w.home,name='app'),path('official/',w.home,name='official'),
 path('app/new/',w.new_report,name='new_report'),path('app/alerts/',w.alerts,name='alerts'),path('reports/<int:pk>/',w.detail,name='detail'),
 path('reports/<int:pk>/delete/',w.delete_report,name='delete_report'),path('reports/<int:pk>/transition/',w.transition,name='transition'),path('reports/<int:pk>/comment/',w.comment,name='comment'),
 path('bulletin/',w.bulletin,name='bulletin'),path('bulletin/<int:pk>/delete/',w.ann_delete,name='ann_delete'),path('photos/<int:pk>/',w.photo,name='photo')]
