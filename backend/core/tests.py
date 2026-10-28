import io,tempfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.db import IntegrityError,transaction
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase
from core.models import *
TMP=tempfile.mkdtemp()
def png():
    b=io.BytesIO();Image.new('RGB',(8,8)).save(b,'PNG');return SimpleUploadedFile('a.png',b.getvalue(),'image/png')
@override_settings(MEDIA_ROOT=TMP,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,SECURE_SSL_REDIRECT=False,CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}})
class T(APITestCase):
    def setUp(s):
        cache.clear();s.b=Barangay.objects.create(name='A',city_municipality='C',province='P');s.b2=Barangay.objects.create(name='B',city_municipality='C',province='P')
        for n in ['Safety','Emergency','Flooding']: Category.objects.get_or_create(name=n,defaults={'is_emergency':n=='Emergency'})
        s.d=Department.objects.create(barangay=s.b,name='Maintenance')
        s.res=User.objects.create_user('r@x.ph','Str0ng#Pass1',full_name='Res One',barangay=s.b);s.off=User.objects.create_user('o@x.ph','Str0ng#Pass1',full_name='Off One',barangay=s.b,role='Official')
        s.lgu=User.objects.create_user('lgu@x.ph','Str0ng#Pass1',full_name='LGU User',barangay=s.b,role='LGU')
        s.other=User.objects.create_user('z@x.ph','Str0ng#Pass1',full_name='Other',barangay=s.b2,role='Official')
    def post(s,cat='Flooding',**x):
        d=dict(title='Flood',description='x'*25,category=Category.objects.get(name=cat).id,latitude='10.3',longitude='123.8',photos=[png()]);d.update(x)
        return s.client.post('/api/reports/',d,format='multipart')
    def test_register_forces_resident_and_needs_consent(s):
        d=dict(email='n@x.ph',password='Str0ng#Pass1',full_name='New',barangay=s.b.id,role='Official')
        assert s.client.post('/api/auth/register/',{**d,'consent':False},format='json').status_code==400
        r=s.client.post('/api/auth/register/',{**d,'consent':True},format='json');assert r.status_code==201 and r.data['role']=='Resident'
    def test_weak_password_rejected(s):
        assert s.client.post('/api/auth/register/',dict(email='n@x.ph',password='12345678',full_name='New',barangay=s.b.id,consent=True),format='json').status_code==400
    def test_login_lockout(s):
        for _ in range(5): s.client.post('/api/auth/login/',dict(email='r@x.ph',password='bad'),format='json')
        assert s.client.post('/api/auth/login/',dict(email='r@x.ph',password='Str0ng#Pass1'),format='json').status_code==429
    def test_requires_login(s): assert s.client.get('/api/reports/').status_code in(401,403)
    def test_lgu_cannot_submit_reports(s):
        s.client.force_login(s.lgu)
        assert s.post().status_code==403
    def test_report_rules(s):
        s.client.force_login(s.res)
        assert s.post(description='short').status_code==400 and s.post(photos=[]).status_code==400
        r=s.post('Emergency');assert r.status_code==201 and r.data['priority']=='Urgent' and r.data['status']=='Pending'
    def test_daily_limit(s):
        s.client.force_login(s.res)
        for _ in range(5): assert s.post().status_code==201
        assert s.post().status_code==400
    def test_status_flow_and_rules(s):
        s.client.force_login(s.res);i=s.post().data['id'];u=f'/api/reports/{i}/transition/'
        assert s.client.post(u,dict(status='Assigned',department=s.d.id),format='json').status_code==403  # resident blocked
        s.client.force_login(s.off)
        assert s.client.post(u,dict(status='Resolved'),format='json').status_code==400  # skip step
        assert s.client.post(u,dict(status='Assigned'),format='json').status_code==400  # needs dept
        assert s.client.post(u,dict(status='Assigned',department=s.d.id),format='json').status_code==200
        assert s.client.post(u,dict(status='In Progress'),format='json').status_code==200
        assert s.client.post(u,dict(status='Resolved'),format='json').status_code==400  # needs comment
        assert s.client.post(u,dict(status='Resolved',comment='Fixed the drain'),format='json').status_code==200
        assert s.client.post(u,dict(status='Rejected',comment='nope nope'),format='json').status_code==400  # final
        r=Report.objects.get(pk=i);assert r.history.count()==4 and r.reporter.notifications.count()==3 and r.resolved_at
    def test_barangay_isolation(s):
        s.client.force_login(s.res);i=s.post().data['id'];s.client.force_login(s.other)
        assert s.client.get(f'/api/reports/{i}/').status_code==404 and s.client.post(f'/api/reports/{i}/transition/',dict(status='Rejected',comment='abcdef'),format='json').status_code==404
    def test_anonymous_and_privacy(s):
        s.client.force_login(s.res);i=s.post('Safety',is_suspicious_activity=True).data['id']
        v=User.objects.create_user('v@x.ph','Str0ng#Pass1',full_name='Viewer',barangay=s.b);s.client.force_login(v)
        assert s.client.get(f'/api/reports/{i}/').data['reporter']=='Anonymous'
        s.client.force_login(s.off);d=s.client.get(f'/api/reports/{i}/').data;assert d['reporter']=='Res One' and d['reporter_contact']['email']=='r@x.ph'  # officials see the reporter (BR-29/28)
    def test_delete_only_own_pending(s):
        s.client.force_login(s.res);i=s.post().data['id'];s.client.force_login(s.off);assert s.client.delete(f'/api/reports/{i}/').status_code==403
        s.client.force_login(s.res);assert s.client.delete(f'/api/reports/{i}/').status_code==204
    def test_db_constraints(s):
        with s.assertRaises(IntegrityError),transaction.atomic(): Report.objects.create(reporter=s.res,barangay=s.b,category=Category.objects.first(),title='t',description='short',latitude=999,longitude=0)
        with s.assertRaises(IntegrityError),transaction.atomic(): User.objects.create_user('q@x.ph','x',full_name='Q',role='Hacker',barangay=s.b)
    def test_announcement_rules(s):
        s.client.force_login(s.res);assert s.client.post('/api/announcements/',dict(title='abc',body='hello',type='Advisory'),format='json').status_code==403
        s.client.force_login(s.off);assert s.client.post('/api/announcements/',dict(title='abc',body='hello',type='Event',event_date='2000-01-01'),format='json').status_code==400
        assert s.client.post('/api/announcements/',dict(title='abc',body='hello',type='Advisory'),format='json').status_code==201
    def test_api_root(s):
        r=s.client.get('/api/')
        assert r.status_code==200 and r.data['service']=='BantayBarangay API'
    def test_tisa_available_for_registration(s):
        r=s.client.get('/api/barangays/')
        assert r.status_code==200 and {'id':Barangay.objects.get(name='Tisa',city_municipality='Cebu City').id,'name':'Tisa, Cebu City'} in r.data
    def test_healthz(s): assert s.client.get('/healthz').status_code==200
