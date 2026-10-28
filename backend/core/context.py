def site(request):
    u=getattr(request,'user',None)
    if not u or not u.is_authenticated: return {}
    return {'home_name':'official' if u.is_official else 'app','unread':u.notifications.filter(is_read=False).count(),'role_label':'Admin' if u.is_superuser else u.role}
