from django.contrib import admin
from django import forms


class ReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"}

    def has_delete_permission(self, request, obj=None):
        return False


class AuditReasonForm(forms.ModelForm):
    audit_reason = forms.CharField(label="Audit reason", min_length=5, max_length=500)

    class Meta:
        fields = "__all__"


class AuditedAdmin(admin.ModelAdmin):
    form = AuditReasonForm

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from operations.models import AuditEvent

        AuditEvent.objects.create(actor=request.user, action="admin_updated" if change else "admin_created", object_type=obj._meta.label_lower, object_id=obj.pk, reason=form.cleaned_data["audit_reason"])

    def has_delete_permission(self, request, obj=None):
        return False
