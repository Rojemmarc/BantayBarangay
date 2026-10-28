import mimetypes
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.forms import PasswordResetForm
from django.core.cache import cache
from django.db import connection,transaction
from django.db.models import Case,Count,IntegerField,Q,When
from django.http import FileResponse,Http404,JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import action,api_view,permission_classes,throttle_classes
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.parsers import FormParser,JSONParser,MultiPartParser
from rest_framework.permissions import AllowAny,BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.viewsets import ViewSet
from .models import *
from .serializers import *

class IsOfficial(BasePermission):
    def has_permission(s,r,v): return bool(r.user.is_authenticated and r.user.is_official)
class IsBarangayManager(BasePermission):
    def has_permission(s,r,v): return bool(r.user.is_authenticated and r.user.can_manage_reports)
class IsReportCollaborator(BasePermission):
    def has_permission(s,r,v): return bool(r.user.is_authenticated and (r.user.is_official or r.user.role=='Volunteer'))
class IsLGU(BasePermission):
    def has_permission(s,r,v): return bool(r.user.is_authenticated and r.user.is_lgu)
class IsNotLGU(BasePermission):
    def has_permission(s,r,v): return bool(r.user.is_authenticated and not r.user.is_lgu)
class Auth(ScopedRateThrottle): scope_attr='auth_scope'
def authed(f): return throttle_classes([Auth])(f)

def user_out(u): return dict(id=u.id,email=u.email,full_name=u.full_name,role=u.role,is_official=u.is_official,barangay=dict(id=u.barangay_id,name=str(u.barangay)) if u.barangay else None)
def healthz(r):
    with connection.cursor() as c: c.execute('SELECT 1')
    return JsonResponse({'ok':True})
@ensure_csrf_cookie
def csrf(r): return JsonResponse({'ok':True})

@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(r):
    return Response({
        'service': 'BantayBarangay API',
        'status': 'ok',
        'routes': {
            'auth': {
                'register': '/api/auth/register/',
                'login': '/api/auth/login/',
                'logout': '/api/auth/logout/',
                'me': '/api/auth/me/',
                'password_reset': '/api/auth/password-reset/',
            },
            'reports': '/api/reports/',
            'barangays': '/api/barangays/',
            'meta': '/api/meta/',
            'stats': '/api/stats/',
            'announcements': '/api/announcements/',
            'notifications': '/api/notifications/',
            'ranking': '/api/ranking/',
            'lgu_summary': '/api/lgu/summary/',
        },
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def barangays(r): return Response([dict(id=b.id,name=str(b)) for b in Barangay.objects.all()])
@api_view(['POST'])
@permission_classes([AllowAny])
@authed
def register(r):
    s=RegisterS(data=r.data); s.is_valid(raise_exception=True); d=s.validated_data
    from django.utils import timezone
    u=User.objects.create_user(d['email'],d['password'],full_name=d['full_name'],barangay=d['barangay'],contact_number=d.get('contact_number',''),role='Resident',consent_at=timezone.now())  # BR-04: role forced
    return Response(user_out(u),status=201)
@api_view(['POST'])
@permission_classes([AllowAny])
@authed
def login_view(r):
    email=str(r.data.get('email','')).strip().lower();key=f'lock:{email}'
    if cache.get(key,0)>=5: return Response({'detail':'Too many attempts. Try again in 5 minutes.'},status=429)
    u=authenticate(r,username=email,password=str(r.data.get('password','')))
    if not u:
        try: cache.set(key,cache.get(key,0)+1,300)
        except Exception: pass
        return Response({'detail':'Incorrect email or password.'},status=400)  # BR-05 via is_active; generic message
    cache.delete(key); login(r,u); return Response(user_out(u))
@api_view(['POST'])
def logout_view(r): logout(r); return Response(status=204)
@api_view(['GET'])
def me(r): return Response(user_out(r.user))
@api_view(['POST'])
@permission_classes([AllowAny])
@authed
def password_reset(r):
    f=PasswordResetForm({'email':str(r.data.get('email',''))})
    if f.is_valid(): f.save(request=r._request,use_https=not r._request.META.get('HTTP_HOST','').startswith('localhost'))
    return Response({'detail':'If an account exists, a reset link has been sent.'})  # no enumeration

@api_view(['GET'])
def meta(r): return Response(dict(categories=[dict(id=c.id,name=c.name) for c in Category.objects.all()],departments=[dict(id=d.id,name=d.name) for d in Department.objects.filter(barangay=r.user.barangay)]))

def rep_out(r,u,full=False):
    off=u.can_manage_reports;anon=not off and r.reporter_id!=u.id  # BR-29
    d=dict(id=r.id,title=r.title,category=r.category.name,status=r.status,priority=r.priority,is_emergency=r.is_emergency,mine=r.reporter_id==u.id,
      reporter='Anonymous' if anon else r.reporter.full_name,department=r.department.name if r.department else None,assigned_to=r.assigned_to.full_name if r.assigned_to and (off or r.assigned_to_id==u.id) else None,created_at=r.created_at,latitude=float(r.latitude),longitude=float(r.longitude))
    if off and not anon: d['reporter_contact']=dict(email=r.reporter.email,phone=r.reporter.contact_number)  # BR-28
    if full:
        d.update(description=r.description,location_note=r.location_note,resolved_at=r.resolved_at,quality_rating=r.quality_rating,photos=[f'/api/photos/{p.id}/' for p in r.photos.all()],
         history=[dict(status=h.new_status,by='Anonymous' if anon and h.changed_by_id==r.reporter_id else h.changed_by.full_name,at=h.changed_at) for h in r.history.select_related('changed_by')],
         comments=[dict(by=c.author.full_name,text=c.comment_text,at=c.created_at) for c in r.comments.select_related('author')])
    return d
def scope(u):
    q=Report.objects.all() if u.is_superuser and not u.barangay_id else Report.objects.filter(barangay=u.barangay)
    return q.select_related('reporter','category','department','assigned_to')  # BR-19/20
def reports_for(u):
    if u.is_lgu: raise PermissionDenied('LGU accounts can only view aggregated report data.')
    if u.is_superuser or u.role=='Official': return scope(u)
    if u.is_staff_member: return scope(u).filter(assigned_to=u)
    if u.role=='Volunteer': return scope(u)
    return Report.objects.filter(reporter=u).select_related('reporter','category','department','assigned_to')

class ReportViewSet(ViewSet):
    parser_classes=[MultiPartParser,FormParser,JSONParser]
    def list(s,r):
        q=reports_for(r.user);p=r.query_params
        if p.get('mine')=='1': q=q.filter(reporter=r.user)
        if p.get('category'): q=q.filter(category__name=p['category'])
        if p.get('status') in STATUSES: q=q.filter(status=p['status'])
        if p.get('q'): q=q.filter(Q(title__icontains=p['q'][:100])|Q(description__icontains=p['q'][:100])|Q(location_note__icontains=p['q'][:100]))
        for k,op in(('date_from','gte'),('date_to','lte')):
            d=parse_date(p.get(k,'')) if p.get(k) else None
            if d: q=q.filter(**{f'created_at__date__{op}':d})
        q=q.annotate(o=Case(When(is_emergency=True,status__in=['Pending','Assigned','In Progress'],then=0),default=1,output_field=IntegerField())).order_by('o','-created_at')
        try: pg=max(1,int(p.get('page',1)))
        except ValueError: pg=1
        return Response(dict(count=q.count(),page=pg,results=[rep_out(x,r.user) for x in q[(pg-1)*25:pg*25]]))
    def retrieve(s,r,pk=None): return Response(rep_out(get_object_or_404(reports_for(r.user).prefetch_related('photos'),pk=pk),r.user,True))
    @transaction.atomic
    def create(s,r):
        u=r.user
        if not u.is_reporter: raise PermissionDenied('Only residents and volunteers can submit reports.')
        from django.utils import timezone;import datetime
        if Report.objects.filter(reporter=u,created_at__gte=timezone.now()-datetime.timedelta(days=1)).count()>=5: raise ValidationError('Daily limit reached: 5 reports per day.')  # BR-10
        ser=ReportCreateS(data=r.data);ser.is_valid(raise_exception=True);d=ser.validated_data;c=d['category']
        rep=Report.objects.create(reporter=u,barangay=u.barangay,category=c,title=d['title'],description=d['description'],latitude=d['latitude'],longitude=d['longitude'],location_note=d.get('location_note',''),
          is_suspicious_activity=d.get('is_suspicious_activity',False) and c.name=='Safety',is_emergency=c.is_emergency,priority='Urgent' if c.is_emergency else 'Normal')  # BR-11/21
        for f in d['photos']: ReportPhoto.objects.create(report=rep,image=f,file_type=f.image.format,file_size_kb=max(1,f.size//1024))
        StatusHistory.objects.create(report=rep,changed_by=u,old_status=None,new_status='Pending')
        return Response(rep_out(rep,u,True),status=201)
    def destroy(s,r,pk=None):
        if not r.user.is_reporter: raise PermissionDenied('Only residents and volunteers can delete reports.')
        rep=get_object_or_404(reports_for(r.user),pk=pk)
        if rep.reporter_id!=r.user.id or rep.status!='Pending': raise PermissionDenied('Only your own Pending reports can be deleted.')  # BR-18
        rep.delete();return Response(status=204)
    @action(detail=True,methods=['post'],permission_classes=[IsOfficial])
    def transition(s,r,pk=None):
        u=r.user
        with transaction.atomic():
            rep=get_object_or_404(reports_for(u).select_for_update(of=('self',)),pk=pk)  # row lock: no double transitions
            dept=get_object_or_404(Department,pk=r.data['department'],barangay=rep.barangay) if r.data.get('department') else None
            assignee=None
            if u.can_manage_reports and r.data.get('status')=='Assigned':
                assignee_id=str(r.data.get('assigned_to',''))
                if not assignee_id.isdigit(): raise ValidationError('Select a staff member to assign this report to.')
                assignee=get_object_or_404(User,pk=assignee_id,barangay=rep.barangay,role='Staff',is_active=True)
            rep.change_status(r.data.get('status'),u,r.data.get('comment',''),dept)
            if assignee:
                rep.assigned_to=assignee;rep.save(update_fields=['assigned_to','updated_at'])
                Notification.objects.create(user=assignee,report=rep,message=f'You were assigned report "{rep.title}".')
        return Response(rep_out(rep,r.user,True))
    @action(detail=True,methods=['post'],permission_classes=[IsReportCollaborator])
    def comment(s,r,pk=None):
        u=r.user
        if not (u.can_manage_reports or u.is_staff_member or u.role=='Volunteer'): raise PermissionDenied()
        rep=get_object_or_404(reports_for(u),pk=pk);t=str(r.data.get('text','')).strip()
        if len(t)<2: raise ValidationError('Write a comment.')
        if u.role=='Volunteer' and rep.status not in ['Pending','Assigned','In Progress']: raise ValidationError('Community updates can only be added to active reports.')
        Comment.objects.create(report=rep,author=u,comment_text=t[:1000],is_official=u.is_official)
        label='official update' if u.is_official else 'community update'
        if rep.reporter_id!=u.id: Notification.objects.create(user=rep.reporter,report=rep,message=f'New {label} on "{rep.title}".')
        if rep.assigned_to_id and rep.assigned_to_id!=u.id: Notification.objects.create(user=rep.assigned_to,report=rep,message=f'New {label} on "{rep.title}".')
        return Response(rep_out(rep,r.user,True))
    @action(detail=True,methods=['post'],permission_classes=[IsBarangayManager])
    def rate(s,r,pk=None):
        rep=get_object_or_404(scope(r.user),pk=pk)
        try: n=int(r.data.get('rating'))
        except (TypeError,ValueError): raise ValidationError('Rating must be 1 to 5.')
        if rep.status!='Resolved' or not 1<=n<=5: raise ValidationError('Only Resolved reports can be rated 1 to 5.')  # BR-27
        rep.quality_rating=n;rep.save(update_fields=['quality_rating','updated_at']);return Response(rep_out(rep,r.user,True))

@api_view(['GET'])
def photo(r,pk):
    p=get_object_or_404(ReportPhoto.objects.select_related('report'),pk=pk)
    get_object_or_404(reports_for(r.user),pk=p.report_id)
    return FileResponse(p.image.open('rb'),content_type=mimetypes.guess_type(p.image.name)[0] or 'application/octet-stream')

@api_view(['GET'])
def stats(r):
    u=r.user;q=reports_for(u);n=lambda s:q.filter(status=s).count();tot=q.count()
    d=dict(total=tot,pending=n('Pending'),in_progress=n('Assigned')+n('In Progress'),resolved=n('Resolved'),rejected=n('Rejected'),active_emergencies=scope(u).filter(is_emergency=True,status__in=['Pending','Assigned','In Progress']).count())
    if u.can_manage_reports:
        from django.db.models import F;import datetime
        w=q.filter(resolved_at__isnull=False,resolved_at__lte=F('created_at')+datetime.timedelta(days=7)).count();d['resolved_within_7_days_pct']=round(w/tot*100) if tot else 0  # BR-30
    return Response(d)

@api_view(['GET','POST'])
def announcements(r):
    u=r.user
    if r.method=='POST':
        if not u.can_manage_reports: raise PermissionDenied()
        s=AnnS(data=r.data);s.is_valid(raise_exception=True);a=Announcement.objects.create(barangay=u.barangay,posted_by=u,**s.validated_data);return Response(dict(id=a.id),status=201)  # BR-24
    from django.utils import timezone
    q=Announcement.objects.filter(barangay=u.barangay).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).select_related('posted_by').order_by('-created_at')
    if r.query_params.get('all')!='1': q=q[:5]
    return Response([dict(id=a.id,title=a.title,body=a.body,type=a.type,event_date=a.event_date,by=a.posted_by.full_name,created_at=a.created_at) for a in q])
@api_view(['DELETE'])
@permission_classes([IsBarangayManager])
def announcement_delete(r,pk): get_object_or_404(Announcement,pk=pk,barangay=r.user.barangay).delete();return Response(status=204)
@api_view(['GET','POST'])
def notifications(r):
    q=r.user.notifications.order_by('-created_at')
    if r.method=='POST': q.filter(is_read=False).update(is_read=True);return Response(status=204)
    return Response(dict(unread=q.filter(is_read=False).count(),results=[dict(id=n.id,report=n.report_id,message=n.message,is_read=n.is_read,created_at=n.created_at) for n in q[:50]]))
@api_view(['GET'])
@permission_classes([IsNotLGU])
def ranking(r):  # BR-26
    rows=User.objects.filter(barangay=r.user.barangay,role__in=['Resident','Volunteer']).annotate(t=Count('reports',filter=~Q(reports__status='Rejected')),rs=Count('reports',filter=Q(reports__status='Resolved')),hi=Count('reports',filter=Q(reports__quality_rating__gte=4)&~Q(reports__status='Rejected')))
    out=sorted(([x.full_name,x.t+2*x.rs+x.hi] for x in rows),key=lambda z:-z[1])[:5];return Response([dict(name=n,points=p) for n,p in out])

@api_view(['GET'])
@permission_classes([IsLGU])
def lgu_summary(r):
    reports=Report.objects.all()
    return Response({
        'total':reports.count(),
        'by_status':list(reports.values('status').annotate(count=Count('id')).order_by('status')),
        'by_category':list(reports.values('category__name').annotate(count=Count('id')).order_by('-count','category__name')),
        'by_barangay':list(reports.values('barangay__name','barangay__city_municipality','barangay__province').annotate(count=Count('id')).order_by('-count','barangay__name')),
    })
