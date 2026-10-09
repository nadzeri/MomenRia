from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django import forms

from operations.models import AuditEvent

from .models import User


class AuditedUserChangeForm(UserChangeForm):
    audit_reason = forms.CharField(label="Audit reason", min_length=5, max_length=500)


class AuditedUserCreationForm(AdminUserCreationForm):
    audit_reason = forms.CharField(label="Audit reason", min_length=5, max_length=500)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = AuditedUserChangeForm
    add_form = AuditedUserCreationForm
    ordering = ("email",)
    list_display = ("email", "email_verified", "is_active", "is_staff", "last_login", "created_at")
    list_filter = ("is_active", "email_verified", "is_staff", "is_superuser")
    date_hierarchy = "created_at"
    fieldsets = ((None, {"fields": ("email", "password")}), ("Status", {"fields": ("email_verified", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}), ("Dates", {"fields": ("last_login",)}), ("Audit", {"fields": ("audit_reason",)}))
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "is_staff", "audit_reason")}),)
    readonly_fields = ("email_verified", "last_login")
    search_fields = ("email", "=id")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(actor=request.user, action="admin_updated" if change else "admin_created", object_type=obj._meta.label_lower, object_id=obj.pk, reason=form.cleaned_data["audit_reason"])
