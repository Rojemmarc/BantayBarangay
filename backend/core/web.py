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
            if r.user.is_official!=official: raise PermissionDenied
            return f(r,*a,**k)
        return w
    return deco
def scope(u): return Report.objects.filter(barangay=u.barangay).select_related('reporter','category','department')  # BR-19/20
def deco_report(x,u):
    x.who='Anonymous' if x.is_suspicious_activity and not u.is_official and x.reporter_id!=u.id else x.reporter.full_name  # BR-29
    x.active=x.is_emergency and x.status in ACTIVE
    return x

def index(r): return redirect(('official' if r.user.is_official else 'app') if r.user.is_authenticated else 'login')
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
    q=scope(u) if u.is_official else Report.objects.filter(reporter=u);c=lambda *s:q.filter(status__in=s).count();t=q.count()
    d=dict(total=t,pending=c('Pending'),progress=c('Assigned','In Progress'),resolved=c('Resolved'),emergencies=scope(u).filter(is_emergency=True,status__in=ACTIVE).count())
    if u.is_official:
        w=q.filter(resolved_at__isnull=False,resolved_at__lte=F('created_at')+datetime.timedelta(days=7)).count();d['pct7']=round(w/t*100) if t else 0  # BR-30
    return d
@login_required
def home(r):
    u=r.user
    if r.resolver_match.url_name!=('official' if u.is_official else 'app'): return redirect('index')
    g=r.GET;q=scope(u)
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
    return render(r,'home.html',{'page':page,'stats':stats(u),'cats':Category.objects.all(),'statuses':STATUSES,'g':g,'qs':keep.urlencode(),'filtered':any(g.get(k) for k in('q','category','status','date_from','date_to','mine'))})

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
    u=r.user;x=deco_report(get_object_or_404(scope(u).prefetch_related('photos'),pk=pk),u)
    return render(r,'detail.html',{'x':x,'history':[(h,'Anonymous' if x.who=='Anonymous' and h.changed_by_id==x.reporter_id else h.changed_by.full_name) for h in x.history.select_related('changed_by')],'comments':x.comments.select_related('author'),'nx':TRANS.get(x.status,[]),'depts':Department.objects.filter(barangay=u.barangay) if u.is_official else []})
@role(True)
@require_POST
def transition(r,pk):
    d=None;p=r.POST.get('department','')
    if p.isdigit(): d=get_object_or_404(Department,pk=p,barangay=r.user.barangay)
    with transaction.atomic():
        x=get_object_or_404(scope(r.user).select_for_update(of=('self',)),pk=pk)
        try: x.change_status(r.POST.get('status'),r.user,r.POST.get('comment',''),d);messages.success(r,f'Status updated to {x.status}.')
        except ValidationError as e: messages.error(r,' '.join(flat(e.detail)))
    return redirect('detail',pk=pk)
@role(True)
@require_POST
def comment(r,pk):
    x=get_object_or_404(scope(r.user),pk=pk);t=r.POST.get('comment','').strip()
    if len(t)<2: messages.error(r,'Write a comment first.')
    else:
        Comment.objects.create(report=x,author=r.user,comment_text=t[:1000],is_official=True)
        Notification.objects.create(user=x.reporter,report=x,message=f'New official comment on "{x.title}".');messages.success(r,'Comment posted.')
    return redirect('detail',pk=pk)
@role(False)
@require_POST
def delete_report(r,pk):
    x=get_object_or_404(scope(r.user),pk=pk)
    if x.reporter_id!=r.user.id or x.status!='Pending': raise PermissionDenied  # BR-18
    x.delete();messages.success(r,'Report deleted.');return redirect('app')
@role(False)
def alerts(r):
    items=list(r.user.notifications.order_by('-created_at')[:50]);r.user.notifications.filter(is_read=False).update(is_read=True)
    return render(r,'alerts.html',{'items':items})
@login_required
def bulletin(r):
    u=r.user;errs=[]
    if r.method=='POST':
        if not u.is_official: raise PermissionDenied  # BR-24
        s=AnnS(data=r.POST)
        if s.is_valid(): Announcement.objects.create(barangay=u.barangay,posted_by=u,**s.validated_data);messages.success(r,'Posted.');return redirect('bulletin')
        errs=flat(s.errors)
    q=Announcement.objects.filter(barangay=u.barangay).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).select_related('posted_by').order_by('-created_at')
    al=r.GET.get('all')=='1'
    rows=User.objects.filter(barangay=u.barangay,role__in=['Resident','Volunteer']).annotate(t=Count('reports',filter=~Q(reports__status='Rejected')),rs=Count('reports',filter=Q(reports__status='Resolved')),hi=Count('reports',filter=Q(reports__quality_rating__gte=4)&~Q(reports__status='Rejected')))
    rank=sorted(([x.full_name,x.t+2*x.rs+x.hi] for x in rows),key=lambda z:-z[1])[:5]  # BR-26
    return render(r,'bulletin.html',{'items':q if al else q[:5],'more':q.count()>5,'all':al,'errors':errs,'rank':rank,'v':r.POST})
@role(True)
@require_POST
def ann_delete(r,pk): get_object_or_404(Announcement,pk=pk,barangay=r.user.barangay).delete();return redirect('bulletin')
@login_required
def photo(r,pk):
    p=get_object_or_404(ReportPhoto.objects.select_related('report'),pk=pk)
    if p.report.barangay_id!=r.user.barangay_id: from django.http import Http404;raise Http404
    return FileResponse(p.image.open('rb'),content_type=mimetypes.guess_type(p.image.name)[0] or 'application/octet-stream')
