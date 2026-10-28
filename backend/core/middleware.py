POLICY="default-src 'self'; img-src 'self' data: blob: https://*.tile.openstreetmap.org https://tile.openstreetmap.de; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
class CSPMiddleware:
    def __init__(self,get): self.get=get
    def __call__(self,request):
        r=self.get(request)
        if not request.path.startswith('/django-admin'): r.headers.setdefault('Content-Security-Policy',POLICY)
        return r
class PrivateNoCacheMiddleware:
    def __init__(self,get): self.get=get
    def __call__(self,request):
        r=self.get(request)
        if request.user.is_authenticated:
            r.headers['Cache-Control']='private, no-store, no-cache, max-age=0, must-revalidate'
            r.headers['Pragma']='no-cache'
            r.headers['Expires']='0'
        return r
class HealthMiddleware:
    def __init__(self,get): self.get=get
    def __call__(self,request):
        if request.path=='/healthz':
            from .views import healthz
            return healthz(request)
        return self.get(request)