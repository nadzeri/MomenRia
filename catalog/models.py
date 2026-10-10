import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TemplateVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        PAUSED = "paused", "Paused"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField()
    version = models.PositiveIntegerField()
    name = models.CharField(max_length=120)
    occasion = models.CharField(max_length=80)
    people_count = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=240)
    attire = models.CharField(max_length=120, blank=True)
    sample_asset = models.CharField(max_length=240)
    sample_sha256 = models.CharField(max_length=64, blank=True)
    asset_width = models.PositiveIntegerField(default=1448)
    asset_height = models.PositiveIntegerField(default=1086)
    coordinate_convention = models.CharField(max_length=40, default="normalized_top_left")
    configuration_hash = models.CharField(max_length=64)
    generation_config = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    evidence_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("slug", "version"), name="catalog_template_slug_version_unique"),
            models.CheckConstraint(condition=models.Q(people_count__gte=1, people_count__lte=4), name="catalog_people_count_1_to_4"),
            models.CheckConstraint(condition=~Q(status="published") | Q(evidence_approved=True), name="catalog_published_requires_evidence"),
        ]
        ordering = ("slug", "-version")

    def clean(self):
        if self.status == self.Status.PUBLISHED and not self.evidence_approved:
            raise ValidationError("Published templates require approved evidence.")
        if self.status == self.Status.PUBLISHED and (not self.pk or self.slots.count() != self.people_count):
            raise ValidationError("Published templates require exactly one stable slot per person.")
        if self.status == self.Status.PUBLISHED and settings.APP_ENV == "production":
            from momenria.http import ApiError
            from processing.prompts import validate_character_configuration

            try:
                validate_character_configuration(self)
            except ApiError as error:
                raise ValidationError(error.code) from error
            approved = self.pk and self.benchmark_evidence.filter(approved=True, configuration_hash=self.configuration_hash, people_count=self.people_count).exists()
            if not approved:
                raise ValidationError("Published templates require matching approved benchmark evidence.")
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            immutable = ("slug", "version", "name", "people_count", "sample_asset", "sample_sha256", "asset_width", "asset_height", "coordinate_convention", "configuration_hash", "generation_config")
            if prior and prior.status in (self.Status.PUBLISHED, self.Status.PAUSED):
                if self.status == self.Status.DRAFT or any(getattr(prior, field) != getattr(self, field) for field in immutable):
                    raise ValidationError("Published template versions are immutable; create a new version.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class FaceSlot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(TemplateVersion, on_delete=models.CASCADE, related_name="slots")
    position = models.PositiveSmallIntegerField()
    x = models.DecimalField(max_digits=6, decimal_places=5)
    y = models.DecimalField(max_digits=6, decimal_places=5)
    width = models.DecimalField(max_digits=6, decimal_places=5, default=0.12)
    height = models.DecimalField(max_digits=6, decimal_places=5, default=0.16)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("template", "position"), name="catalog_template_position_unique"),
            models.CheckConstraint(condition=models.Q(x__gte=0, x__lte=1, y__gte=0, y__lte=1), name="catalog_slot_center_normalized"),
            models.CheckConstraint(condition=models.Q(width__gt=0, width__lte=1, height__gt=0, height__lte=1), name="catalog_slot_size_normalized"),
            models.CheckConstraint(condition=models.Q(position__gte=1, position__lte=4), name="catalog_slot_position_1_to_4"),
        ]
        ordering = ("position",)

    def save(self, *args, **kwargs):
        quantum = Decimal("0.00001")
        for field in ("x", "y", "width", "height"):
            setattr(self, field, Decimal(str(getattr(self, field))).quantize(quantum))
        self.full_clean()
        if self.template.status in (TemplateVersion.Status.PUBLISHED, TemplateVersion.Status.PAUSED):
            prior = type(self).objects.filter(pk=self.pk).first()
            if not prior or any(getattr(prior, field) != getattr(self, field) for field in ("position", "x", "y", "width", "height")):
                raise ValidationError("Published face slots are immutable; create a new template version.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.template.status in (TemplateVersion.Status.PUBLISHED, TemplateVersion.Status.PAUSED):
            raise ValidationError("Published face slots cannot be deleted; create a new template version.")
        return super().delete(*args, **kwargs)


class Offer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=100)
    price_idr = models.PositiveIntegerField()
    purchase_unit = models.CharField(max_length=20, choices=(("result_download", "Legacy download"), ("generation", "New picture")), default="result_download")
    active = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(price_idr__gte=1), name="catalog_offer_price_positive"),
            models.CheckConstraint(condition=models.Q(active=False) | models.Q(activated_at__isnull=False), name="catalog_active_offer_has_activation"),
            models.UniqueConstraint(fields=("purchase_unit",), condition=models.Q(active=True, purchase_unit="generation"), name="catalog_one_generation_offer"),
        ]

    def save(self, *args, **kwargs):
        if self.price_idr <= 0:
            raise ValidationError("Offer price must be positive.")
        if self.active and not self.activated_at:
            self.activated_at = timezone.now()
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.activated_at and (prior.version != self.version or prior.name != self.name or prior.price_idr != self.price_idr or prior.activated_at != self.activated_at or prior.purchase_unit != self.purchase_unit):
                raise ValidationError("Active offers are immutable; create a new version.")
        return super().save(*args, **kwargs)
