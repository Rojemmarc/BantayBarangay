"""Server-rendered pages. Business rules live in models.py / serializers.py and are reused here."""
import datetime,mimetypes
from functools import wraps
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case,Count,F,IntegerField,Q,When
from django.http import FileResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from rest_framework.exceptions import ValidationError
from .models import *
from .serializers import AnnS,RegisterS,ReportCreateS

ACTIVE=['Pending','Assigned','In Progress']
def flat(e,k=None,out=None):
    out=[] if out is None else out
    if isinstance(e,dict):
        for kk,v in e.items(): flat(v,kk,out)
    elif isinstance(e,(list,tuple)):
        for v in e: flat(v,k,out)
    else: out.append(f"{k.replace('_',' ').capitalize()}: {e}" if k and k!='non_field_errors' else str(e))
    return out
def role(official):
    def deco(f):
        @login_required
        @wraps(f)
        def w(r,*a,**k):
            allowed=r.user.is_official if official else r.user.is_reporter
            if not allowed: raise PermissionDenied
            return f(r,*a,**k)
        return w
    return deco
def scope(u):
    q=Report.objects.all() if u.is_superuser and not u.barangay_id else Report.objects.filter(barangay=u.barangay)
    return q.select_related('reporter','category','department','assigned_to')  # BR-19/20
def reports_for(u):
    if u.is_lgu: raise PermissionDenied('LGU accounts can only view aggregated report data.')
    if u.is_superuser or u.role=='Official': return scope(u)
    if u.is_staff_member: return scope(u).filter(assigned_to=u)
    if u.role=='Volunteer': return scope(u)
    return Report.objects.filter(reporter=u).select_related('reporter','category','department','assigned_to')
def deco_report(x,u):
    x.who='Anonymous' if x.reporter_id!=u.id and (x.is_suspicious_activity or not u.can_manage_reports) else x.reporter.full_name  # BR-29
    x.active=x.is_emergency and x.status in ACTIVE
    return x

def index(r):
    if not r.user.is_authenticated: return redirect('login')
    return redirect('lgu_dashboard' if r.user.is_lgu else 'official' if r.user.is_official else 'app')
def legal(r): return render(r,'legal.html')
def login_view(r):
    if r.user.is_authenticated: return redirect('index')
    err=''
    if r.method=='POST':
        email=r.POST.get('email','').strip().lower();key=f'lock:{email}'
        if cache.get(key,0)>=5: err='Too many attempts. Try again in 5 minutes.'
        else:
            u=authenticate(r,username=email,password=r.POST.get('password',''))
            if u:
                cache.delete(key);login(r,u);n=r.POST.get('next','')
                if n and url_has_allowed_host_and_scheme(n,allowed_hosts={r.get_host()},require_https=r.is_secure()): return redirect(n)
                return redirect('index')
            try: cache.set(key,cache.get(key,0)+1,300)
            except Exception: pass
            err='Incorrect email or password.'
    return render(r,'auth/login.html',{'error':err,'next':r.GET.get('next','')})
@require_POST
def logout_view(r): logout(r);return redirect('login')
def register_view(r):
    errs=[]
    if r.method=='POST':
        s=RegisterS(data=r.POST)
        if r.POST.get('password')!=r.POST.get('password2'): errs.append('Passwords do not match.')
        elif s.is_valid():
            d=s.validated_data
            User.objects.create_user(d['email'],d['password'],full_name=d['full_name'],barangay=d['barangay'],contact_number=d.get('contact_number',''),role='Resident',consent_at=timezone.now())  # BR-04
            messages.success(r,'Account created. Please log in.');return redirect('login')
        else: errs=flat(s.errors)
    return render(r,'auth/register.html',{'errors':errs,'barangays':Barangay.objects.all(),'v':r.POST})
def forgot(r):
    sent=False
    if r.method=='POST':
        f=PasswordResetForm({'email':r.POST.get('email','')})
        if f.is_valid(): f.save(request=r,use_https=r.is_secure())
        sent=True  # same answer whether or not the account exists
    return render(r,'auth/forgot.html',{'sent':sent})

def stats(u):
    q=reports_for(u);c=lambda *s:q.filter(status__in=s).count();t=q.count()
    d=dict(total=t,pending=c('Pending'),progress=c('Assigned','In Progress'),resolved=c('Resolved'),emergencies=scope(u).filter(is_emergency=True,status__in=ACTIVE).count())
    if u.can_manage_reports:
        w=q.filter(resolved_at__isnull=False,resolved_at__lte=F('created_at')+datetime.timedelta(days=7)).count();d['pct7']=round(w/t*100) if t else 0  # BR-30
    return d
@login_required
def home(r):
    u=r.user
    if u.is_lgu: return redirect('lgu_dashboard')
    if r.resolver_match.url_name!=('official' if u.is_official else 'app'): return redirect('index')
    g=r.GET;q=reports_for(u)
    if g.get('mine')=='1' and not u.is_official: q=q.filter(reporter=u)
    if g.get('category'): q=q.filter(category__name=g['category'])
    if g.get('status') in STATUSES: q=q.filter(status=g['status'])
    if g.get('q'): t=g['q'][:100];q=q.filter(Q(title__icontains=t)|Q(description__icontains=t)|Q(location_note__icontains=t))
    for k,op in(('date_from','gte'),('date_to','lte')):
        d=parse_date(g.get(k,'')) if g.get(k) else None
        if d: q=q.filter(**{f'created_at__date__{op}':d})
    q=q.annotate(o=Case(When(is_emergency=True,status__in=ACTIVE,then=0),default=1,output_field=IntegerField())).order_by('o','-created_at')
    page=Paginator(q,25).get_page(g.get('page'));[deco_report(x,u) for x in page]
    keep=g.copy();keep.pop('page',None)
    return render(r,'home.html',{'page':page,'stats':stats(u),'cats':Category.objects.all(),'statuses':STATUSES,'g':g,'qs':keep.urlencode(),'filtered':any(g.get(k) for k in('q','category','status','date_from','date_to','mine')),'staff_members':User.objects.filter(barangay=u.barangay,role='Staff',is_active=True) if u.can_manage_reports else []})

@login_required
@login_required
def lgu_dashboard(r):
    if not r.user.is_lgu: raise PermissionDenied
    totals=Report.objects.values('status').annotate(count=Count('id')).order_by('status')
    categories=Report.objects.values('category__name').annotate(count=Count('id')).order_by('-count','category__name')
    barangays=Report.objects.values('barangay__name','barangay__city_municipality','barangay__province').annotate(count=Count('id')).order_by('-count','barangay__name')
    return render(r,'lgu_dashboard.html',{'total':Report.objects.count(),'statuses':totals,'categories':categories,'barangays':barangays})

@role(False)
def new_report(r):
    errs=[]
    if r.method=='POST':
        u=r.user;data=r.POST.copy();data.setlist('photos',r.FILES.getlist('photos'))
        if Report.objects.filter(reporter=u,created_at__gte=timezone.now()-datetime.timedelta(days=1)).count()>=5: errs=['Daily limit reached: 5 reports per day.']  # BR-10
        else:
            s=ReportCreateS(data=data)
            if s.is_valid():
                d=s.validated_data;c=d['category']
                with transaction.atomic():
                    rep=Report.objects.create(reporter=u,barangay=u.barangay,category=c,title=d['title'],description=d['description'],latitude=d['latitude'],longitude=d['longitude'],location_note=d.get('location_note',''),
                      is_suspicious_activity=d.get('is_suspicious_activity',False) and c.name=='Safety',is_emergency=c.is_emergency,priority='Urgent' if c.is_emergency else 'Normal')
                    for f in d['photos']: ReportPhoto.objects.create(report=rep,image=f,file_type=f.image.format,file_size_kb=max(1,f.size//1024))
                    StatusHistory.objects.create(report=rep,changed_by=u,old_status=None,new_status='Pending')
                messages.success(r,'Report submitted.');return redirect('detail',pk=rep.pk)
            errs=flat(s.errors)
    return render(r,'new_report.html',{'cats':Category.objects.all(),'errors':errs,'v':r.POST})
@login_required
def detail(r,pk):
    u=r.user;x=deco_report(get_object_or_404(reports_for(u).prefetch_related('photos'),pk=pk),u)
    return render(r,'detail.html',{'x':x,'history':[(h,'Anonymous' if x.who=='Anonymous' and h.changed_by_id==x.reporter_id else h.changed_by.full_name) for h in x.history.select_related('changed_by')],'comments':x.comments.select_related('author'),'nx':TRANS.get(x.status,[]),'depts':Department.objects.filter(barangay=x.barangay) if u.can_manage_reports else [],'staff_members':User.objects.filter(barangay=x.barangay,role='Staff',is_active=True) if u.can_manage_reports else []})
@role(True)
@require_POST
def transition(r,pk):
    u=r.user;p=r.POST.get('department','');assignee_id=r.POST.get('assigned_to','')
    with transaction.atomic():
        x=get_object_or_404(reports_for(u).select_for_update(of=('self',)),pk=pk)
        try:
            d=get_object_or_404(Department,pk=p,barangay=x.barangay) if p.isdigit() else None
            assignee=get_object_or_404(User,pk=assignee_id,barangay=x.barangay,role='Staff',is_active=True) if u.can_manage_reports and r.POST.get('status')=='Assigned' and assignee_id.isdigit() else None
            if u.can_manage_reports and r.POST.get('status')=='Assigned' and not assignee: raise ValidationError('Select a staff member to assign this report to.')
            x.change_status(r.POST.get('status'),u,r.POST.get('comment',''),d)
            if assignee:
                x.assigned_to=assignee;x.save(update_fields=['assigned_to','updated_at'])
                Notification.objects.create(user=assignee,report=x,message=f'You were assigned report "{x.title}".')
            messages.success(r,f'Status updated to {x.status}.')
        except ValidationError as e: messages.error(r,' '.join(flat(e.detail)))
    return redirect('detail',pk=pk)
@login_required
@require_POST
def comment(r,pk):
    u=r.user
    if not (u.can_manage_reports or u.is_staff_member or u.role=='Volunteer'): raise PermissionDenied
    x=get_object_or_404(reports_for(u),pk=pk);t=r.POST.get('comment','').strip()
    if len(t)<2: messages.error(r,'Write a comment first.')
    elif u.role=='Volunteer' and x.status not in ACTIVE: messages.error(r,'Community updates can only be added to active reports.')
    else:
        Comment.objects.create(report=x,author=u,comment_text=t[:1000],is_official=u.is_official)
        label='official update' if u.is_official else 'community update'
        if x.reporter_id!=u.id: Notification.objects.create(user=x.reporter,report=x,message=f'New {label} on "{x.title}".')
        if x.assigned_to_id and x.assigned_to_id!=u.id: Notification.objects.create(user=x.assigned_to,report=x,message=f'New {label} on "{x.title}".')
        messages.success(r,'Comment posted.')
    return redirect('detail',pk=pk)
@role(False)
@require_POST
def delete_report(r,pk):
    x=get_object_or_404(scope(r.user),pk=pk)
    if x.reporter_id!=r.user.id or x.status!='Pending': raise PermissionDenied  # BR-18
    x.delete();messages.success(r,'Report deleted.');return redirect('app')
@login_required
def alerts(r):
    if not (r.user.is_staff_member or r.user.is_reporter): raise PermissionDenied
    items=list(r.user.notifications.order_by('-created_at')[:50]);r.user.notifications.filter(is_read=False).update(is_read=True)
    return render(r,'alerts.html',{'items':items})
@login_required
def bulletin(r):
    u=r.user;errs=[]
    if r.method=='POST':
        if not u.can_manage_reports: raise PermissionDenied  # BR-24
        s=AnnS(data=r.POST)
        if s.is_valid(): Announcement.objects.create(barangay=u.barangay,posted_by=u,**s.validated_data);messages.success(r,'Posted.');return redirect('bulletin')
        errs=flat(s.errors)
    q=Announcement.objects.filter(barangay=u.barangay).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).select_related('posted_by').order_by('-created_at')
    al=r.GET.get('all')=='1'
    rows=User.objects.filter(barangay=u.barangay,role__in=['Resident','Volunteer']).annotate(t=Count('reports',filter=~Q(reports__status='Rejected')),rs=Count('reports',filter=Q(reports__status='Resolved')),hi=Count('reports',filter=Q(reports__quality_rating__gte=4)&~Q(reports__status='Rejected')))
    rank=sorted(([x.full_name,x.t+2*x.rs+x.hi] for x in rows),key=lambda z:-z[1])[:5]  # BR-26
    return render(r,'bulletin.html',{'items':q if al else q[:5],'more':q.count()>5,'all':al,'errors':errs,'rank':rank,'v':r.POST})
@login_required
@require_POST
def ann_delete(r,pk):
    if not r.user.can_manage_reports: raise PermissionDenied
    get_object_or_404(Announcement,pk=pk,barangay=r.user.barangay).delete();return redirect('bulletin')
@login_required
def photo(r,pk):
    p=get_object_or_404(ReportPhoto.objects.select_related('report','report__reporter','report__category'),pk=pk)
    get_object_or_404(reports_for(r.user),pk=p.report_id)
    if not r.user.is_superuser and p.report.barangay_id!=r.user.barangay_id: raise Http404
    return FileResponse(p.image.open('rb'),content_type=mimetypes.guess_type(p.image.name)[0] or 'application/octet-stream')
