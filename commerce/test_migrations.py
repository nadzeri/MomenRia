from datetime import timedelta

from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from momenria.http import ApiError


class PricingMigrationTests(TransactionTestCase):
    old = [("catalog", "0008_friendly_descriptions"), ("commerce", "0002_refund_request_hash"), ("processing", "0005_unlimited_portrait_jobs")]

    def test_legacy_cohorts_keep_receipts_revocations_and_lifetime_usage(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(self.old)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        apps = executor.loader.project_state(self.old).apps
        User = apps.get_model("accounts", "User")
        Offer = apps.get_model("catalog", "Offer")
        Template = apps.get_model("catalog", "TemplateVersion")
        Project = apps.get_model("projects", "Project")
        Result = apps.get_model("projects", "ResultVersion")
        Allowance = apps.get_model("processing", "Allowance")
        Job = apps.get_model("processing", "Job")
        Order = apps.get_model("commerce", "Order")
        Entitlement = apps.get_model("commerce", "Entitlement")
        Refund = apps.get_model("commerce", "Refund")
        owner = User.objects.create(email="migration@example.com", password="!", email_verified=True)
        offer = Offer.objects.create(version=10, name="Historical download", price_idr=19900, active=True, activated_at=timezone.now())
        template = Template.objects.create(slug="migration", version=1, name="Legacy", people_count=1, configuration_hash="a" * 64, generation_config={"model": "fake"})
        project = Project.objects.create(owner=owner, offer=offer, template=template, state="active")
        results = []
        for number, status in enumerate(("ready", "deleted", "expired"), 1):
            result = Result.objects.create(project=project, kind="creation", number=number, status=status, source_snapshot={}, region_snapshot={}, configuration_hash="a" * 64, expires_at=timezone.now() + timedelta(days=1), synthetic=False)
            results.append(result)
        Result.objects.create(project=project, kind="creation", number=4, status="ready", source_snapshot={}, region_snapshot={}, configuration_hash="a" * 64, expires_at=timezone.now() + timedelta(days=1), synthetic=True)
        allowance = Allowance.objects.create(owner=owner, kind="creation", policy_version="old", consumed_at=timezone.now())
        Job.objects.create(owner=owner, project=project, result=results[0], allowance=allowance, operation="creation", state="ready", input_snapshot={}, deletion_epoch=0, estimated_cost_idr=1500, next_run_at=timezone.now())
        pending_job = Job.objects.create(owner=owner, project=project, operation="creation", state="queued", input_snapshot={}, deletion_epoch=0, estimated_cost_idr=1500, next_run_at=timezone.now())
        orders = []
        for result, state in ((results[0], "paid"), (results[1], "pending")):
            orders.append(Order.objects.create(owner=owner, project=project, result=result, offer=offer, merchant_reference=f"MR-MIGRATE-{state}", amount_idr=19900, payment_state=state, result_id_snapshot=result.id, result_sha256="b" * 64, result_width=2048, result_height=1536, expires_at=timezone.now() + timedelta(minutes=15)))
        Entitlement.objects.create(owner=owner, order=orders[0], result=results[0], result_id_snapshot=results[0].id, revoked_at=timezone.now())
        Refund.objects.create(order=orders[0], amount_idr=19900, reason="Historical completed refund", idempotency_key="old-refund", state="succeeded", requested_by=owner)
        MigrationExecutor(connection).migrate(latest)
        from accounts.models import User as CurrentUser
        from catalog.models import Offer as CurrentOffer
        from processing.models import Job as CurrentJob
        from processing.quota import initialize_trial_allowances, pricing_for
        from .models import Entitlement as CurrentEntitlement, Order as CurrentOrder, Refund as CurrentRefund
        self.assertEqual(CurrentOrder.objects.get(pk=orders[0].id).amount_idr, 19900)
        self.assertEqual(CurrentOrder.objects.get(pk=orders[1].id).payment_state, "pending")
        self.assertEqual(CurrentRefund.objects.get(idempotency_key="old-refund").state, "succeeded")
        self.assertIsNotNone(CurrentEntitlement.objects.get(order_id=orders[0].id).revoked_at)
        self.assertFalse(CurrentOffer.objects.get(pk=offer.id).active)
        generation = CurrentOffer.objects.get(purchase_unit="generation")
        self.assertEqual(generation.price_idr, 9900)
        self.assertFalse(generation.active)
        current_owner = CurrentUser.objects.get(pk=owner.pk)
        with self.assertRaises(ApiError):
            initialize_trial_allowances(current_owner)
        CurrentJob.objects.filter(pk=pending_job.pk).update(state="failed")
        self.assertEqual(pricing_for(current_owner)["free_used"], 3)
        with self.assertRaises(DatabaseError), transaction.atomic():
            CurrentOffer.objects.filter(pk=offer.pk).update(price_idr=9900)
