from django.contrib import admin

from momenria.admin import ReadOnlyAdmin

from .models import AssignmentHistory, CharacterSheet, Consent, Feedback, MediaAsset, Project, ResultVersion, SlotAssignment, SourceAsset


@admin.register(SourceAsset)
class SourceAssetAdmin(ReadOnlyAdmin):
    list_display = ("id", "project", "status", "validation_code", "expires_at")
    list_filter = ("status", "validation_code")
    readonly_fields = ("content_sha256", "width", "height", "size_bytes", "uploaded_at")
    exclude = ("file", "thumbnail")


@admin.register(CharacterSheet)
class CharacterSheetAdmin(ReadOnlyAdmin):
    list_display = ("id", "project", "source", "mode", "status", "expires_at")
    exclude = ("file", "input_snapshot")


@admin.register(ResultVersion)
class ResultVersionAdmin(ReadOnlyAdmin):
    exclude = ("source_snapshot",)


@admin.register(MediaAsset)
class MediaAssetAdmin(ReadOnlyAdmin):
    exclude = ("file",)


for model in (Project, Consent, SlotAssignment, AssignmentHistory, Feedback):
    admin.site.register(model, ReadOnlyAdmin)
