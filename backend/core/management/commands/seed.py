from django.core.management.base import BaseCommand
from core.models import *
class Command(BaseCommand):
    help='Create reference data. --demo adds demo users (never in production).'
    def add_arguments(s,p):
        p.add_argument('--demo',action='store_true');p.add_argument('--barangay',default='Barangay Demo');p.add_argument('--city',default='Cebu City');p.add_argument('--province',default='Cebu')
    def handle(s,*a,**o):
        b,_=Barangay.objects.get_or_create(name=o['barangay'],city_municipality=o['city'],defaults={'province':o['province']})
        for n in ['Infrastructure','Safety','Sanitation','Flooding','Noise','Emergency']: Category.objects.get_or_create(name=n,defaults={'is_emergency':n=='Emergency'})
        for n in ['Maintenance','Sanitation','Peace and Order','Health']: Department.objects.get_or_create(barangay=b,name=n)
        if o['demo']:
            for e,n,r in [('resident@demo.ph','Maria Santos','Resident'),('official@demo.ph','Juan Dela Cruz','Official')]:
                if not User.objects.filter(email=e).exists(): User.objects.create_user(e,'DemoPass#2026x',full_name=n,role=r,barangay=b)
        s.stdout.write('Seeded.')
