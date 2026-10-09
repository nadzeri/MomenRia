import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Project(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="projects")
    template = models.ForeignKey("catalog.TemplateVersion", on_delete=models.PROTECT, related_name="projects")
    offer = models.ForeignKey("catalog.Offer", on_delete=models.PROTECT, related_name="projects")
    selected_result = models.ForeignKey("ResultVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="selected_by_projects")
    revision = models.PositiveIntegerField(default=1)
    deletion_epoch = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=16, choices=State.choices, default=State.DRAFT)
    assisted = models.BooleanField(default=False)
    acquisition_source = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=("owner", "state"))]


class Consent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="consents")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="consents")
    text_version = models.CharField(max_length=40)
    granted = models.BooleanField()
    granted_at = models.DateTimeField(auto_now_add=True)


def source_upload_path(instance, filename):
    return f"sources/{instance.project_id}/{instance.id}.jpg"


def source_thumbnail_path(instance, filename):
    return f"sources/{instance.project_id}/{instance.id}-thumbnail.jpg"


class SourceAsset(models.Model):
    class Status(models.TextChoices):
        STAGING = "staging", "Staging"
        REVIEW = "review", "Review required"
        READY = "ready", "Ready"
        INVALID = "invalid", "Invalid"
        EXPIRED = "expired", "Expired"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="sources")
    consent = models.ForeignKey(Consent, on_delete=models.PROTECT, related_name="sources")
    upload_key = models.CharField(max_length=120)
    content_sha256 = models.CharField(max_length=64)
    file = models.FileField(upload_to=source_upload_path, max_length=255)
    thumbnail = models.FileField(upload_to=source_thumbnail_path, max_length=255, blank=True)
    thumbnail_sha256 = models.CharField(max_length=64, blank=True)
    original_name = models.CharField(max_length=180)
    format = models.CharField(max_length=12)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    size_bytes = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.STAGING)
    validation_code = models.CharField(max_length=80, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("project", "upload_key"), name="projects_source_upload_key_unique")]
        indexes = [models.Index(fields=("project", "status")), models.Index(fields=("expires_at", "status"))]


def character_sheet_upload_path(instance, filename):
    return f"characters/{instance.project_id}/{instance.id}.jpg"


class CharacterSheet(models.Model):
    class Mode(models.TextChoices):
        SOURCE_LAYOUT = "source_layout", "Source layout"
        GENERATED = "generated", "AI generated views"

    class Status(models.TextChoices):
        PREPARING = "preparing", "Preparing"
        REVIEW = "review", "Review required"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="character_sheets")
    source = models.ForeignKey(SourceAsset, on_delete=models.PROTECT, related_name="character_sheets")
    version = models.PositiveIntegerField()
    mode = models.CharField(max_length=16, choices=Mode.choices)
    recipe_hash = models.CharField(max_length=64)
    input_snapshot = models.JSONField()
    file = models.FileField(upload_to=character_sheet_upload_path, max_length=255, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    panel_provenance = models.JSONField(default=list)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PREPARING)
    synthetic = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("source", "recipe_hash", "version"), name="projects_sheet_source_recipe_version")]
        indexes = [models.Index(fields=("project", "status")), models.Index(fields=("expires_at", "status"))]

    def save(self, *args, **kwargs):
        if self.source.project_id != self.project_id:
            raise ValidationError("Character sheet source must belong to its project.")
        prior = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if prior:
            immutable = ("project_id", "source_id", "version", "mode", "recipe_hash", "input_snapshot", "expires_at")
            if prior.sha256:
                immutable += ("sha256", "width", "height", "panel_provenance", "synthetic")
                if str(prior.file) != str(self.file):
                    raise ValidationError("Character sheet files are immutable.")
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Character sheet inputs and completed output are immutable.")
        return super().save(*args, **kwargs)


class SlotAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="assignments")
    slot = models.ForeignKey("catalog.FaceSlot", on_delete=models.PROTECT, related_name="assignments")
    source = models.ForeignKey(SourceAsset, on_delete=models.PROTECT, related_name="assignments")
    character_sheet = models.ForeignKey(CharacterSheet, null=True, blank=True, on_delete=models.PROTECT, related_name="assignments")
    revision = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("project", "slot"), name="projects_assignment_project_slot_unique"),
            models.UniqueConstraint(fields=("project", "source"), name="projects_assignment_project_source_unique"),
        ]


class AssignmentHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="assignment_history")
    revision = models.PositiveIntegerField()
    assignments = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("project", "revision"), name="projects_history_revision_unique")]


class ResultVersion(models.Model):
    class Status(models.TextChoices):
        QUARANTINED = "quarantined", "Quarantined"
        READY = "ready", "Ready"
        EXPIRED = "expired", "Expired"
        DELETED = "deleted", "Deleted"

    class Kind(models.TextChoices):
        CREATION = "creation", "Creation"
        CORRECTION = "correction", "Correction"
        GREETING = "greeting", "Greeting"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="results")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    generation_root = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="derivatives")
    source_snapshot = models.JSONField()
    region_snapshot = models.JSONField()
    configuration_hash = models.CharField(max_length=64)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    greeting = models.CharField(max_length=48, blank=True)
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUARANTINED)
    synthetic = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("project", "number"), name="projects_result_number_unique")]
        indexes = [models.Index(fields=("project", "status")), models.Index(fields=("expires_at", "status"))]

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            immutable = ("project_id", "parent_id", "generation_root_id", "source_snapshot", "region_snapshot", "configuration_hash", "kind", "greeting", "number", "synthetic", "expires_at")
            if prior and any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValueError("Ready result versions are immutable")
        return super().save(*args, **kwargs)


def media_upload_path(instance, filename):
    return f"results/{instance.project_id}/{instance.result_id}/{instance.kind}.jpg"


class MediaAsset(models.Model):
    class Kind(models.TextChoices):
        MASTER = "master", "Master"
        PREVIEW = "preview", "Preview"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="media")
    result = models.ForeignKey(ResultVersion, on_delete=models.PROTECT, related_name="media")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    file = models.FileField(upload_to=media_upload_path, max_length=255)
    sha256 = models.CharField(max_length=64)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    size_bytes = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("result", "kind"), name="projects_result_media_kind_unique")]
        indexes = [models.Index(fields=("expires_at", "deleted_at"))]


class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="feedback")
    result = models.ForeignKey(ResultVersion, on_delete=models.PROTECT, related_name="feedback")
    slot = models.ForeignKey("catalog.FaceSlot", null=True, blank=True, on_delete=models.PROTECT, related_name="feedback")
    issue = models.CharField(max_length=40, blank=True)
    accepted = models.BooleanField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
