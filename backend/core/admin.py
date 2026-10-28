from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from . import models as m

for x in (m.Barangay, m.Department, m.Category, m.Report, m.Announcement):
    admin.site.register(x)


class AddUserForm(BaseUserCreationForm):
    """Creates a user with a properly hashed password (password1/password2)."""
    class Meta:
        model = m.User
        fields = ('email', 'full_name', 'role', 'barangay', 'contact_number')

    def clean_email(self):
        e = self.cleaned_data['email'].strip().lower()
        if m.User.objects.filter(email__iexact=e).exists():
            raise forms.ValidationError('This email is already registered.')
        return e

    def clean(self):
        d = super().clean()
        if not d.get('barangay'):  # DB rule BR-03: every non-superuser belongs to a barangay
            self.add_error('barangay', 'Choose a barangay.')
        return d


class ChangeUserForm(UserChangeForm):
    class Meta:
        model = m.User
        fields = '__all__'

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


@admin.register(m.User)
class UA(UserAdmin):
    add_form = AddUserForm
    form = ChangeUserForm
    list_display = ('email', 'full_name', 'role', 'barangay', 'is_active')
    list_filter = ('role', 'is_active', 'barangay')
    search_fields = ('email', 'full_name')
    ordering = ('email',)
    filter_horizontal = ('groups', 'user_permissions')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),  # "password" shows the hash + a "change password" link
        ('Profile', {'fields': ('full_name', 'role', 'barangay', 'contact_number', 'consent_at')}),
        ('Access', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'full_name', 'role', 'barangay', 'contact_number', 'password1', 'password2')}),)