import hashlib
import io

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from commerce.models import Entitlement, Order, Refund
from momenria.http import ApiError
from operations.models import AuditEvent, SupportTicket
from processing.models import Job
from processing.quota import initialize_trial_allowances
from projects.models import MediaAsset, Project, ResultVersion
from projects.storage import store_bytes_atomically


class Command(BaseCommand):
    help = "Dry-run historical quota/access audit; --apply requires a staff operator and reason"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--operator")
        parser.add_argument("--reason")

    def handle(self, *args, **options):
        applying = options["apply"]
        actor = get_user_model().objects.filter(email=options["operator"], is_staff=True, is_active=True).first()
        if applying and (not actor or not options["reason"] or not options["reason"].strip()):
            raise CommandError("--apply requires --operator (active staff email) and --reason")
        legacy_active = Job.objects.filter(state__in=Job.ACTIVE_STATES, generation_order__isnull=True).filter(Q(allowance__isnull=True) | Q(allowance__trial_slot__isnull=True))
        pending = Order.objects.filter(purpose="result_download", payment_state__in=("creating", "pending", "uncertain"))
        unknown_terminal = sum(order.provider_payload.get("transaction_status") not in {"deny", "cancel", "expire", "refund"} for order in Order.objects.filter(purpose="result_download", payment_state__in=("cancelled", "expired", "failed")).iterator())
        self.stdout.write(f"legacy_active_jobs={legacy_active.count()} legacy_pending_orders={pending.count()} legacy_unverified_terminal_orders={unknown_terminal}")
        if applying and (legacy_active.exists() or pending.exists() or unknown_terminal):
            raise CommandError("Drain or reconcile legacy jobs and pending download payments before applying")
        for owner in get_user_model().objects.order_by("id").iterator():
            try:
                with transaction.atomic():
                    initialize_trial_allowances(owner)
                    if not applying:
                        transaction.set_rollback(True)
                self.stdout.write(f"owner={owner.id} quota=audited")
            except ApiError as error:
                self.stdout.write(f"owner={owner.id} quota={error.code}")
                continue
            roots = ResultVersion.objects.filter(project__owner=owner, project__state=Project.State.ACTIVE, kind="creation", status="ready", synthetic=False, expires_at__gt=timezone.now()).exclude(job__generation_order__isnull=False)
            for root in roots:
                revoked = Entitlement.objects.filter(owner=owner, result_id_snapshot=root.id, revoked_at__isnull=False).exists()
                refunded = Refund.objects.filter(order__result_id_snapshot=root.id, state="succeeded").exists()
                if revoked or refunded:
                    self.stdout.write(f"result={root.id} access=revoked")
                    continue
                for result in [root, *root.derivatives.filter(status="ready", expires_at__gt=timezone.now())]:
                    self.rebuild(result, owner, actor, options["reason"], applying)

    def rebuild(self, result, owner, actor, reason, applying):
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=owner.pk)
            project = Project.objects.select_for_update().get(pk=result.project_id)
            if project.state != Project.State.ACTIVE or result.expires_at <= timezone.now():
                return
            master = result.media.filter(kind="master", deleted_at__isnull=True, expires_at__gt=timezone.now()).first()
            try:
                if not master:
                    raise FileNotFoundError
                with master.file.open("rb") as file:
                    content = file.read()
                if hashlib.sha256(content).hexdigest() != master.sha256:
                    raise OSError("Master checksum differs")
                with Image.open(io.BytesIO(content)) as source:
                    image = source.convert("RGB")
                    image.thumbnail((768, 768), Image.Resampling.LANCZOS)
                data = io.BytesIO()
                image.save(data, "JPEG", quality=88, optimize=True)
            except (OSError, ValueError):
                self.stdout.write(f"result={result.id} master=unavailable")
                if applying:
                    ResultVersion.objects.filter(pk=result.pk).update(status="quarantined")
                    SupportTicket.objects.get_or_create(owner=owner, project=project, subject="File historis tidak tersedia", message=f"File asli hasil {result.id} perlu diperiksa. Tidak ada biaya baru.")
                return
            self.stdout.write(f"result={result.id} master=verified preview=clean")
            if not applying:
                return
            root = result.generation_root or result
            if root.id == result.id and not Entitlement.objects.filter(owner=owner, result_id_snapshot=root.id).exists():
                Entitlement.objects.create(owner=owner, result=root, result_id_snapshot=root.id, grant_source="legacy")
            preview = result.media.filter(kind="preview").first()
            if preview and (preview.deleted_at or preview.expires_at <= timezone.now()):
                return
            preview = preview or MediaAsset(project=project, result=result, kind="preview", expires_at=result.expires_at)
            content = data.getvalue()
            digest = hashlib.sha256(content).hexdigest()
            if preview.sha256 == digest:
                return
            store_bytes_atomically(preview.file, "preview.jpg", content, replace=bool(preview.file.name))
            preview.sha256, preview.width, preview.height, preview.size_bytes = digest, image.width, image.height, len(content)
            preview.save()
            AuditEvent.objects.create(actor=actor, action="pricing.history_reconciled", object_type="result", object_id=result.id, reason=reason[:500], metadata={"master_sha256": master.sha256, "preview_sha256": digest})
