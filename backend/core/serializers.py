from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers as S
from .models import *
class RegisterS(S.Serializer):
    email=S.EmailField();password=S.CharField(write_only=True);full_name=S.CharField(min_length=2,max_length=150)
    barangay=S.PrimaryKeyRelatedField(queryset=Barangay.objects.all());contact_number=S.CharField(max_length=20,required=False,allow_blank=True);consent=S.BooleanField()
    def validate_email(s,v):
        v=v.lower()
        if User.objects.filter(email__iexact=v).exists(): raise S.ValidationError('This email is already registered.')  # BR-01
        return v
    def validate_consent(s,v):
        if not v: raise S.ValidationError('You must accept the Terms and Privacy Policy.')
        return v
    def validate(s,a): validate_password(a['password'],User(email=a['email'],full_name=a['full_name'])); return a
class ReportCreateS(S.Serializer):
    title=S.CharField(min_length=3,max_length=150);description=S.CharField(min_length=20,max_length=2000)  # BR-08
    category=S.PrimaryKeyRelatedField(queryset=Category.objects.all())
    latitude=S.DecimalField(9,6,min_value=-90,max_value=90);longitude=S.DecimalField(9,6,min_value=-180,max_value=180)
    location_note=S.CharField(max_length=255,required=False,allow_blank=True);is_suspicious_activity=S.BooleanField(required=False)
    photos=S.ListField(child=S.ImageField(),min_length=1,max_length=3)  # BR-08/09
    def validate_photos(s,v):
        for f in v:
            if f.size>5*1024*1024 or f.image.format not in('JPEG','PNG'): raise S.ValidationError('Photos must be JPG or PNG, up to 5 MB each.')
        return v
class AnnS(S.Serializer):
    title=S.CharField(min_length=3,max_length=150);body=S.CharField(min_length=5,max_length=2000)
    type=S.ChoiceField(['Announcement','Advisory','Event']);event_date=S.DateField(required=False,allow_null=True)
    def validate(s,a):
        from django.utils import timezone
        if a['type']=='Event' and (not a.get('event_date') or a['event_date']<timezone.localdate()): raise S.ValidationError('Events need a date that is not in the past.')  # BR-25
        return a
