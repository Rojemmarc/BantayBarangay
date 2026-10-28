def site(request):
    u=getattr(request,'user',None)
    if not u or not u.is_authenticated: return {}
    home='lgu_dashboard' if u.is_lgu else 'official' if u.is_official else 'app'
    return {'home_name':home,'unread':u.notifications.filter(is_read=False).count(),'role_label':'Admin' if u.is_superuser else u.role}
