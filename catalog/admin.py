from django.contrib import admin

from momenria.admin import AuditedAdmin

from .models import FaceSlot, Offer, TemplateVersion


class FaceSlotInline(admin.TabularInline):
    model = FaceSlot
    extra = 0


@admin.register(TemplateVersion)
class TemplateVersionAdmin(AuditedAdmin):
    list_display = ("name", "version", "people_count", "status", "evidence_approved")
    list_filter = ("status", "evidence_approved", "people_count")
    inlines = (FaceSlotInline,)


admin.site.register(Offer, AuditedAdmin)
