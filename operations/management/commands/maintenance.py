import time
import logging
from datetime import timedelta
from pathlib import Path
import shutil

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from commerce.models import Entitlement, Order, PaymentEvent
from operations.models import AnalyticsEvent, AuditEvent, DeletionTask, OperationalAlert, OutboxEvent, RateLimitBucket, SupportGrant
from processing.models import AdmissionControl, BudgetReservation, Job, JobAttempt, WorkerControl
from processing.services import budget_committed
from projects.models import CharacterSheet, MediaAsset, Project, ResultVersion, SourceAsset


def remove_file(field):
    if field and field.name:
        field.delete(save=False)


def expire_assets(now):
    for sheet in CharacterSheet.objects.filter(Q(expires_at__lte=now) | Q(source__expires_at__lte=now) | Q(source__consent__granted=False)).exclude(status__in=(CharacterSheet.Status.EXPIRED, CharacterSheet.Status.DELETED)).iterator():
        remove_file(sheet.file)
        CharacterSheet.objects.filter(pk=sheet.pk).update(status=CharacterSheet.Status.EXPIRED, deleted_at=now)
    for source in SourceAsset.objects.filter(expires_at__lte=now, status__in=(SourceAsset.Status.READY, SourceAsset.Status.REVIEW, SourceAsset.Status.STAGING)).iterator():
        remove_file(source.file)
        remove_file(source.thumbnail)
        source.status = SourceAsset.Status.EXPIRED
        source.deleted_at = now
        source.save(update_fields=("status", "deleted_at"))
    for result in ResultVersion.objects.filter(expires_at__lte=now, status=ResultVersion.Status.READY).iterator():
        for media in result.media.filter(deleted_at__isnull=True):
            remove_file(media.file)
            media.deleted_at = now
            media.save(update_fields=("deleted_at",))
        result.status = ResultVersion.Status.EXPIRED
        result.save(update_fields=("status",))
        Entitlement.objects.filter(result_id_snapshot=result.id, revoked_at__isnull=True).update(revoked_at=now)
        Order.objects.filter(result_id_snapshot=result.id).update(fulfillment_state=Order.FulfillmentState.ENDED)


def process_deletions(now):
    tasks = DeletionTask.objects.filter(state__in=(DeletionTask.State.QUEUED, DeletionTask.State.FAILED), next_run_at__lte=now).order_by("next_run_at")[:20]
    for task in tasks:
        try:
            with transaction.atomic():
                task = DeletionTask.objects.select_for_update().get(id=task.id)
                task.state = DeletionTask.State.RUNNING
                task.attempts += 1
                task.save(update_fields=("state", "attempts"))
            project = Project.objects.get(id=task.project_id_snapshot, deletion_epoch=task.deletion_epoch, state=Project.State.DELETED)
            for sheet in project.character_sheets.exclude(status=CharacterSheet.Status.DELETED):
                remove_file(sheet.file)
                CharacterSheet.objects.filter(pk=sheet.pk).update(status=CharacterSheet.Status.DELETED, deleted_at=now)
            for source in project.sources.exclude(status=SourceAsset.Status.DELETED):
                remove_file(source.file)
                remove_file(source.thumbnail)
                source.status = SourceAsset.Status.DELETED
                source.deleted_at = now
                source.save(update_fields=("status", "deleted_at"))
            for media in project.media.filter(deleted_at__isnull=True):
                remove_file(media.file)
                media.deleted_at = now
                media.save(update_fields=("deleted_at",))
            project.results.exclude(status=ResultVersion.Status.DELETED).update(status=ResultVersion.Status.DELETED)
            Entitlement.objects.filter(result_id_snapshot__in=project.results.values("id"), revoked_at__isnull=True).update(revoked_at=now)
            Order.objects.filter(project=project, payment_state__in=(Order.PaymentState.CREATING, Order.PaymentState.PENDING, Order.PaymentState.UNCERTAIN)).update(payment_state=Order.PaymentState.CANCELLED, fulfillment_state=Order.FulfillmentState.ENDED)
            Order.objects.filter(project=project, payment_state=Order.PaymentState.PAID).update(fulfillment_state=Order.FulfillmentState.ENDED)
            task.state = DeletionTask.State.COMPLETE
            task.completed_at = now
            task.error_code = ""
            task.save(update_fields=("state", "completed_at", "error_code"))
            AnalyticsEvent.objects.create(event_id=__import__("uuid").uuid4(), event="deletion_completed", project_id=project.id, dimensions={"deletion_epoch": task.deletion_epoch})
        except Exception as error:
            task.state = DeletionTask.State.FAILED
            task.error_code = type(error).__name__[:80]
            task.next_run_at = now + timedelta(minutes=min(60, 2 ** min(task.attempts, 5)))
            task.save(update_fields=("state", "error_code", "next_run_at"))


def reconcile_expired_leases(now):
    jobs = Job.objects.filter(state__in=(Job.State.DISPATCHING, Job.State.PROCESSING, Job.State.FINALIZING), leased_until__lte=now).order_by("leased_until")[:20]
    for job in jobs:
        with transaction.atomic():
            job = Job.objects.select_for_update().get(id=job.id)
            if job.state not in (Job.State.DISPATCHING, Job.State.PROCESSING, Job.State.FINALIZING) or job.leased_until and job.leased_until > now:
                continue
            attempt = job.attempts.order_by("-number").first()
            if job.state == Job.State.DISPATCHING and attempt and attempt.state == JobAttempt.State.PREPARED:
                attempt.state = JobAttempt.State.FAILED
                attempt.error_code = "worker_lost_before_send"
                attempt.finished_at = now
                attempt.save(update_fields=("state", "error_code", "finished_at"))
                job.state = Job.State.QUEUED
                job.lease_token = None
                job.leased_until = None
                job.heartbeat_at = None
                job.next_run_at = now
                job.error_code = ""
                job.save(update_fields=("state", "lease_token", "leased_until", "heartbeat_at", "next_run_at", "error_code", "updated_at"))
            else:
                if attempt and attempt.state not in (JobAttempt.State.SUCCEEDED, JobAttempt.State.FAILED):
                    attempt.state = JobAttempt.State.UNCERTAIN
                    attempt.error_code = "worker_lease_expired"
                    attempt.finished_at = now
                    attempt.save(update_fields=("state", "error_code", "finished_at"))
                job.state = Job.State.UNCERTAIN
                job.error_code = "worker_lease_expired"
                job.save(update_fields=("state", "error_code", "updated_at"))
                OutboxEvent.objects.create(topic="job.uncertain", payload={"job_id": str(job.id), "project_id": str(job.project_id)})


def deliver_local_outbox(now):
    events = OutboxEvent.objects.filter(delivered_at__isnull=True).order_by("created_at")[:100]
    for event in events:
        with transaction.atomic():
            event = OutboxEvent.objects.select_for_update().get(id=event.id)
            if event.delivered_at:
                continue
            object_id = event.payload.get("order_id") or event.payload.get("job_id") or event.payload.get("project_id")
            try:
                parsed_object_id = __import__("uuid").UUID(object_id) if object_id else None
            except ValueError:
                parsed_object_id = None
            AuditEvent.objects.create(action=event.topic, object_type="outbox", object_id=parsed_object_id, metadata={"outbox_id": str(event.id)})
            event.delivered_at = now
            event.save(update_fields=("delivered_at",))


def cleanup_orphan_media(now):
    root = Path(settings.MEDIA_ROOT)
    referenced = set(SourceAsset.objects.exclude(file="").values_list("file", flat=True))
    referenced.update(SourceAsset.objects.exclude(thumbnail="").values_list("thumbnail", flat=True))
    referenced.update(MediaAsset.objects.exclude(file="").values_list("file", flat=True))
    referenced.update(CharacterSheet.objects.exclude(file="").values_list("file", flat=True))
    cutoff = now.timestamp() - 3600
    inspected = 0
    for directory in (root / "sources", root / "results", root / "characters", root / ".staging"):
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if inspected >= 500:
                return
            if not path.is_file():
                continue
            inspected += 1
            relative = path.relative_to(root).as_posix()
            if relative not in referenced and path.stat().st_mtime < cutoff:
                path.unlink()


def _set_alert(code, active, severity, message, details, now):
    existing = OperationalAlert.objects.filter(code=code).first()
    notify = active and (not existing or not existing.active)
    if active:
        alert, _ = OperationalAlert.objects.update_or_create(code=code, defaults={"severity": severity, "active": True, "message": message, "details": details, "resolved_at": None})
        if notify and settings.ALERT_EMAIL:
            send_mail(f"[MomenRia] {message}", f"{message}\n\n{details}", settings.DEFAULT_FROM_EMAIL, [settings.ALERT_EMAIL], fail_silently=True)
    elif existing and existing.active:
        existing.active = False
        existing.resolved_at = now
        existing.save(update_fields=("active", "resolved_at", "last_seen_at"))


def evaluate_alerts(now):
    media_root = Path(settings.MEDIA_ROOT)
    media_root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(media_root)
    used_percent = round(((usage.total - usage.free) * 100) / usage.total, 2)
    disk_severity = OperationalAlert.Severity.CRITICAL if used_percent >= 90 else OperationalAlert.Severity.WARNING
    _set_alert("disk_pressure", used_percent >= 80, disk_severity, "Penyimpanan media melewati ambang", {"used_percent": used_percent, "free_bytes": usage.free}, now)

    worker = WorkerControl.objects.filter(key="global").first()
    worker_age = (now - worker.heartbeat_at).total_seconds() if worker and worker.heartbeat_at else None
    _set_alert("worker_heartbeat", worker_age is None or worker_age > 60, OperationalAlert.Severity.CRITICAL, "Heartbeat worker tidak tersedia", {"age_seconds": worker_age}, now)

    uncertain = Job.objects.filter(Q(state=Job.State.UNCERTAIN) | Q(state=Job.State.CANCELLED, attempts__state=JobAttempt.State.UNCERTAIN, budget_reservation__state=BudgetReservation.State.RESERVED)).distinct().count()
    _set_alert("uncertain_jobs", uncertain > 0, OperationalAlert.Severity.CRITICAL, "Ada proses AI yang memerlukan rekonsiliasi", {"count": uncertain}, now)

    mismatches = PaymentEvent.objects.filter(verified=False, received_at__lt=now - timedelta(minutes=2)).count()
    _set_alert("payment_mismatch", mismatches > 0, OperationalAlert.Severity.CRITICAL, "Notifikasi pembayaran belum terverifikasi", {"count": mismatches}, now)

    late_deletions = DeletionTask.objects.exclude(state=DeletionTask.State.COMPLETE).filter(created_at__lt=now - timedelta(hours=1)).count()
    _set_alert("deletion_backlog", late_deletions > 0, OperationalAlert.Severity.CRITICAL, "Penghapusan melewati target satu jam", {"count": late_deletions}, now)

    period = timezone.localdate()
    reserved = budget_committed(period)
    control = AdmissionControl.objects.filter(key="global").first()
    budget = min(settings.DAILY_BUDGET_IDR, control.daily_budget_idr) if control else settings.DAILY_BUDGET_IDR
    ratio = float(reserved / budget) if budget else 0
    _set_alert("budget_pressure", budget > 0 and ratio >= .8, OperationalAlert.Severity.WARNING, "Reservasi biaya melewati 80 persen anggaran", {"reserved_idr": str(reserved), "budget_idr": budget}, now)

    marker = Path(settings.BACKUP_MARKER_PATH)
    backup_age = now.timestamp() - marker.stat().st_mtime if marker.exists() else None
    _set_alert("backup_stale", backup_age is None or backup_age > 26 * 3600, OperationalAlert.Severity.CRITICAL, "Cadangan belum terverifikasi dalam 26 jam", {"age_seconds": backup_age}, now)


def reconcile_payments(now):
    from commerce.services import cancel_prepared_job, lock_order, refresh_order
    from momenria.http import ApiError
    if settings.PAYMENT_PROVIDER == "disabled":
        return
    pending = (Order.PaymentState.CREATING, Order.PaymentState.PENDING, Order.PaymentState.UNCERTAIN)
    terminal = (Order.PaymentState.FAILED, Order.PaymentState.CANCELLED, Order.PaymentState.EXPIRED)
    rows = Order.objects.filter(Q(payment_state__in=pending) | Q(payment_state=Order.PaymentState.PAID) & ~Q(fulfillment_state=Order.FulfillmentState.ENDED) | Q(payment_state__in=terminal) & ~Q(provider_payload__transaction_status__in=("deny", "cancel", "expire"))).filter(Q(updated_at__lt=now - timedelta(minutes=1)) | Q(expires_at__lte=now)).order_by("updated_at", "id")[:10]
    for order in list(rows):
        Order.objects.filter(pk=order.pk).update(updated_at=now)
        try:
            if settings.APP_ENV == "test" and settings.PAYMENT_PROVIDER == "fake":
                with transaction.atomic():
                    order = lock_order(order)
                    if order.payment_state in pending and order.expires_at <= now:
                        order.payment_state = Order.PaymentState.EXPIRED
                        order.provider_payload["transaction_status"] = "expire"
                        order.save(update_fields=("payment_state", "provider_payload", "updated_at"))
                        if order.job_id:
                            cancel_prepared_job(order.job, "payment_expired")
            else:
                refresh_order(order)
        except ApiError as error:
            logging.getLogger(__name__).warning("payment reconciliation unavailable order=%s code=%s", order.id, error.code)


def maintain_once():
    now = timezone.now()
    reconcile_expired_leases(now)
    expire_assets(now)
    process_deletions(now)
    deliver_local_outbox(now)
    cleanup_orphan_media(now)
    evaluate_alerts(now)
    SupportGrant.objects.filter(expires_at__lte=now, revoked_at__isnull=True).update(revoked_at=now)
    reconcile_payments(now)
    RateLimitBucket.objects.filter(window_start__lt=now - timedelta(days=2)).delete()


class Command(BaseCommand):
    help = "Run retention, deletion, payment-expiry, and support-grant maintenance"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            maintain_once()
            if options["once"]:
                return
            time.sleep(300)
