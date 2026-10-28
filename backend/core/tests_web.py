import io,tempfile
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client,TestCase,override_settings
from PIL import Image
from core.models import *
TMP=tempfile.mkdtemp()
def png():
    b=io.BytesIO();Image.new('RGB',(8,8)).save(b,'PNG');return SimpleUploadedFile('a.png',b.getvalue(),'image/png')
@override_settings(MEDIA_ROOT=TMP,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,SECURE_SSL_REDIRECT=False,CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}})
class Web(TestCase):
    def setUp(s):
        cache.clear();s.b=Barangay.objects.create(name='A',city_municipality='C',province='P');s.b2=Barangay.objects.create(name='B',city_municipality='C',province='P')
        for n in ['Safety','Emergency','Flooding']: Category.objects.create(name=n,is_emergency=n=='Emergency')
        s.d=Department.objects.create(barangay=s.b,name='Maintenance');P='Str0ng#Pass1'
        s.res=User.objects.create_user('r@x.ph',P,full_name='Res One',barangay=s.b);s.off=User.objects.create_user('o@x.ph',P,full_name='Off One',barangay=s.b,role='Official')
        s.other=User.objects.create_user('z@x.ph',P,full_name='Other',barangay=s.b2,role='Official')
    def rep(s,**x):
        d=dict(category=Category.objects.get(name='Flooding').pk,title='Flood',description='x'*25,latitude='10.3',longitude='123.8',photos=png());d.update(x)
        return s.client.post('/app/new/',d)
    def test_login_redirects_by_role(s):
        r=s.client.post('/login/',{'email':'r@x.ph','password':'Str0ng#Pass1'});assert r.status_code==302 and r.url=='/'
        assert s.client.get('/',follow=True).redirect_chain[-1][0]=='/app/'
        c=Client();c.post('/login/',{'email':'o@x.ph','password':'Str0ng#Pass1'});assert c.get('/',follow=True).redirect_chain[-1][0]=='/official/'
    def test_bad_login_generic_and_lockout(s):
        r=s.client.post('/login/',{'email':'r@x.ph','password':'bad'});assert b'Incorrect email or password.' in r.content
        for _ in range(5): s.client.post('/login/',{'email':'r@x.ph','password':'bad'})
        assert b'Too many attempts' in s.client.post('/login/',{'email':'r@x.ph','password':'Str0ng#Pass1'}).content
    def test_open_redirect_blocked(s):
        r=s.client.post('/login/',{'email':'r@x.ph','password':'Str0ng#Pass1','next':'https://evil.com'});assert r.url=='/'
    def test_pages_need_login_and_roles(s):
        assert s.client.get('/app/').status_code==302 and s.client.get('/bulletin/').status_code==302
        s.client.force_login(s.res);assert s.client.get('/official/',follow=True).redirect_chain[-1][0]=='/app/' and s.client.get('/reports/1/transition/').status_code in(403,405)
        s.client.force_login(s.off);assert s.client.get('/app/new/').status_code==403
    def test_register(s):
        d=dict(full_name='New',email='n@x.ph',password='Zx9#kLm2Qw',password2='Zx9#kLm2Qw',barangay=s.b.pk,role='Official')
        assert b'Terms and Privacy' in s.client.post('/register/',d).content
        assert s.client.post('/register/',{**d,'consent':'on'}).status_code==302;assert User.objects.get(email='n@x.ph').role=='Resident'
    def test_report_flow_and_escaping(s):
        s.client.force_login(s.res);r=s.rep(title='<script>alert(1)</script>');assert r.status_code==302
        page=s.client.get(r.url);assert b'<script>alert(1)' not in page.content and b'&lt;script&gt;' in page.content
        assert b'description' in s.client.post('/app/new/',dict(title='abc',category=1,description='short',latitude='1',longitude='1')).content.lower()
    def test_official_actions(s):
        s.client.force_login(s.res);u=s.rep().url;i=int(u.strip('/').split('/')[-1]);t=f'/reports/{i}/transition/'
        s.client.force_login(s.off)
        assert b'Select a department' in s.client.post(t,{'status':'Assigned'},follow=True).content
        assert b'updated to Assigned' in s.client.post(t,{'status':'Assigned','department':s.d.pk},follow=True).content
        s.client.post(t,{'status':'In Progress'});assert b'comment explaining' in s.client.post(t,{'status':'Resolved'},follow=True).content
        s.client.post(t,{'status':'Resolved','comment':'Fixed the drain'});r=Report.objects.get(pk=i);assert r.status=='Resolved' and r.history.count()==4 and r.reporter.notifications.count()==3
        s.client.force_login(s.res);a=s.client.get('/app/alerts/');assert b'is now Resolved' in a.content and s.res.notifications.filter(is_read=False).count()==0
    def test_isolation_and_photo_privacy(s):
        s.client.force_login(s.res);u=s.rep().url;r=Report.objects.get();s.client.force_login(s.other)
        assert s.client.get(u).status_code==404 and s.client.get(f'/photos/{r.photos.first().pk}/').status_code==404
        s.client.force_login(s.off);assert s.client.get(f'/photos/{r.photos.first().pk}/').status_code==200
    def test_anonymous_reporter(s):
        s.client.force_login(s.res);s.client.post('/app/new/',dict(category=Category.objects.get(name='Safety').pk,title='Odd',description='x'*25,latitude='1',longitude='1',photos=png(),is_suspicious_activity='on'))
        v=User.objects.create_user('v@x.ph','Str0ng#Pass1',full_name='Viewer Person',barangay=s.b);pk=Report.objects.get().pk;s.client.force_login(v)
        h=s.client.get(f'/reports/{pk}/').content;assert b'Anonymous' in h and b'Res One' not in h
    def test_bulletin_rules(s):
        s.client.force_login(s.res);assert s.client.post('/bulletin/',dict(title='abc',body='hello',type='Advisory')).status_code==403
        s.client.force_login(s.off);assert b'not in the past' in s.client.post('/bulletin/',dict(title='abc',body='hello',type='Event',event_date='2000-01-01')).content.replace(b'be in the',b'be in the')
        assert s.client.post('/bulletin/',dict(title='Cleanup',body='hello there',type='Advisory'),follow=True).status_code==200 and b'Cleanup' in s.client.get('/bulletin/').content
    def test_empty_states_and_error_pages(s):
        s.client.force_login(s.res);assert b'No reports yet' in s.client.get('/app/').content
        assert b'Page not found' in s.client.get('/nope/').content
    def test_csrf_enforced(s):
        c=Client(enforce_csrf_checks=True);assert c.post('/login/',{'email':'r@x.ph','password':'Str0ng#Pass1'}).status_code==403
    def test_delete_own_pending(s):
        s.client.force_login(s.res);i=int(s.rep().url.strip('/').split('/')[-1]);assert s.client.post(f'/reports/{i}/delete/').status_code==302 and not Report.objects.exists()
