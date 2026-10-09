import tempfile
import socket
from datetime import timedelta
from unittest.mock import patch

from allauth.mfa.models import Authenticator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import Offer, TemplateVersion
from projects.models import MediaAsset, Project, ResultVersion

from .models import AuditEvent, SupportGrant


@override_settings(PUBLIC_ACCESS=False, TRUSTED_PROXY_HOST="caddy")
class TrustedProxyRateLimitTests(TestCase):
    def setUp(self):
        self.proxy_addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.20.0.5", 0)), (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::5", 0, 0, 0))]
        self.resolver = patch("operations.rate_limit.socket.getaddrinfo", return_value=self.proxy_addresses)
        self.resolver.start()
        self.addCleanup(self.resolver.stop)

    def test_clients_behind_caddy_have_separate_network_limits(self):
        data = {"email": "access@example.com", "subject": "Access help", "message": "Cannot open my account"}
        for _ in range(5):
            response = self.client.post("/api/v1/support/account-access", data, content_type="application/json", REMOTE_ADDR="172.20.0.5", HTTP_X_MOMENRIA_CLIENT_IP="198.51.100.10")
            self.assertEqual(response.status_code, 202)
        self.assertEqual(self.client.post("/api/v1/support/account-access", data, content_type="application/json", REMOTE_ADDR="172.20.0.5", HTTP_X_MOMENRIA_CLIENT_IP="198.51.100.10").status_code, 429)
        self.assertEqual(self.client.post("/api/v1/support/account-access", data, content_type="application/json", REMOTE_ADDR="172.20.0.5", HTTP_X_MOMENRIA_CLIENT_IP="198.51.100.11").status_code, 202)

    def test_spoofed_headers_from_untrusted_peer_use_remote_address(self):
        from .rate_limit import client_network

        request = RequestFactory().get("/", REMOTE_ADDR="198.51.100.90", HTTP_X_MOMENRIA_CLIENT_IP="203.0.113.42", HTTP_X_FORWARDED_FOR="203.0.113.43")
        self.assertEqual(client_network(request), "198.51.100.90")

    def test_malformed_or_missing_client_header_uses_proxy_address(self):
        from .rate_limit import client_network

        for value in ("invalid", "198.51.100.10,198.51.100.11", "198.51.100.10:80", ""):
            request = RequestFactory().get("/", REMOTE_ADDR="172.20.0.5", HTTP_X_MOMENRIA_CLIENT_IP=value, HTTP_X_FORWARDED_FOR="203.0.113.42")
            self.assertEqual(client_network(request), "172.20.0.5")

    def test_dns_failure_uses_remote_address(self):
        from .rate_limit import client_network

        request = RequestFactory().get("/", REMOTE_ADDR="172.20.0.5", HTTP_X_MOMENRIA_CLIENT_IP="198.51.100.10")
        with patch("operations.rate_limit.socket.getaddrinfo", side_effect=socket.gaierror("DNS unavailable")):
            self.assertEqual(client_network(request), "172.20.0.5")

    @override_settings(TRUSTED_PROXY_HOST="")
    def test_proxy_headers_are_ignored_by_default(self):
        from .rate_limit import client_network

        request = RequestFactory().get("/", REMOTE_ADDR="172.20.0.5", HTTP_X_MOMENRIA_CLIENT_IP="198.51.100.10")
        self.assertEqual(client_network(request), "172.20.0.5")

    def test_ipv6_proxy_and_client_addresses_are_normalized(self):
        from .rate_limit import client_network

        request = RequestFactory().get("/", REMOTE_ADDR="fd00:0:0:0:0:0:0:5", HTTP_X_MOMENRIA_CLIENT_IP="2001:db8:0:0:0:0:0:42")
        self.assertEqual(client_network(request), "2001:db8::42")

    def test_authenticated_owner_limit_survives_client_address_change(self):
        from momenria.http import ApiError
        from .rate_limit import check_rate_limit

        owner = User.objects.create_user("rate-owner@example.com", "strong-password")
        request = RequestFactory().post("/", REMOTE_ADDR="172.20.0.5", HTTP_X_MOMENRIA_CLIENT_IP="198.51.100.10")
        request.user = owner
        check_rate_limit(request, "proxy_test", limit=1, seconds=3600)
        request.META["HTTP_X_MOMENRIA_CLIENT_IP"] = "198.51.100.11"
        with self.assertRaises(ApiError) as context:
            check_rate_limit(request, "proxy_test", limit=1, seconds=3600)
        self.assertEqual(context.exception.status, 429)


@override_settings(PUBLIC_ACCESS=False)
class SupportConversationTests(TestCase):
    def setUp(self):
        from .models import SupportTicket

        self.owner = User.objects.create_user("conversation@example.com", "strong-password", email_verified=True)
        self.other = User.objects.create_user("different@example.com", "strong-password", email_verified=True)
        self.ticket = SupportTicket.objects.create(owner=self.owner, subject="Need help", message="My photo needs checking", status=SupportTicket.Status.ACTION_REQUIRED, owner_visible_reply="Please explain the issue")

    def test_reply_is_owner_only_and_preserves_staff_reply(self):
        from .models import SupportReply, SupportTicket

        url = f"/api/v1/support/tickets/{self.ticket.id}/replies"
        self.assertEqual(self.client.post(url, {"message": "The first face is wrong"}, content_type="application/json").status_code, 401)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {"message": "The first face is wrong"}, content_type="application/json").status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.post(url, {"message": "The first face is wrong"}, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, SupportTicket.Status.WAITING)
        item = self.client.get("/api/v1/support/tickets").json()["items"][0]
        self.assertEqual(item["reply"], "Please explain the issue")
        self.assertEqual(item["messages"][0]["message"], "The first face is wrong")
        self.assertEqual(item["messages"][0]["created_at"], response.json()["created_at"])
        reply = SupportReply.objects.get(id=response.json()["id"])
        reply.message = "Edited reply"
        with self.assertRaises(ValueError):
            reply.save()

    def test_replies_cannot_be_mutated_with_bulk_updates(self):
        from django.db import DatabaseError, transaction
        from .models import SupportReply

        reply = SupportReply.objects.create(ticket=self.ticket, message="Original owner reply")
        with self.assertRaises(DatabaseError), transaction.atomic():
            SupportReply.objects.filter(id=reply.id).update(message="Changed reply")
        reply.refresh_from_db()
        self.assertEqual(reply.message, "Original owner reply")

    def test_reply_validation_and_rate_limit(self):
        from .models import RateLimitBucket

        self.client.force_login(self.owner)
        url = f"/api/v1/support/tickets/{self.ticket.id}/replies"
        for data in ({"message": 123}, {"message": "short"}, {"message": "x" * 2001}, {"message": "Valid message", "status": "resolved"}):
            self.assertEqual(self.client.post(url, data, content_type="application/json").status_code, 400)
        RateLimitBucket.objects.filter(action="support_reply").update(count=20)
        self.assertEqual(self.client.post(url, {"message": "Valid message"}, content_type="application/json").status_code, 429)


@override_settings(PUBLIC_ACCESS=False)
class AccountAccessRequestTests(TestCase):
    def test_receipt_does_not_disclose_account_existence_and_reaches_staff_inbox(self):
        from django.contrib import admin
        from .models import AccountAccessRequest

        User.objects.create_user("exists@example.com", "strong-password")
        receipts = []
        for email in ("exists@example.com", "missing@example.com"):
            response = self.client.post("/api/v1/support/account-access", {"email": email, "subject": "Cannot sign in", "message": "I cannot open my account"}, content_type="application/json")
            self.assertEqual(response.status_code, 202)
            receipts.append(response.json())
        self.assertEqual(receipts[0], receipts[1])
        self.assertTrue(receipts[0]["received"])
        self.assertEqual(AccountAccessRequest.objects.count(), 2)
        self.assertIn(AccountAccessRequest, admin.site._registry)
        self.assertEqual(self.client.get("/api/v1/support/account-access").status_code, 405)

    def test_validation_csrf_and_network_rate_limit(self):
        from django.test import Client
        from .models import AccountAccessRequest, RateLimitBucket

        url = "/api/v1/support/account-access"
        data = {"email": "valid@example.com", "subject": "Sign in help", "message": "Cannot access my account"}
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, data, content_type="application/json").status_code, 403)
        for index, override in enumerate(({"email": "invalid"}, {"subject": ""}, {"message": "short"}, {"message": 123}, {"message": "x" * 2001}, {"subject": "x" * 121}, {"image_access": True})):
            self.assertEqual(self.client.post(url, {**data, **override}, content_type="application/json", REMOTE_ADDR="127.0.0.1" if index == 0 else f"192.0.2.{index}").status_code, 400)
        self.assertFalse(AccountAccessRequest.objects.exists())
        RateLimitBucket.objects.filter(action="account_access").update(count=5)
        response = self.client.post(url, data, content_type="application/json")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(response.json()["retry_after_seconds"], 0)
        self.assertEqual(self.client.post(url, data, content_type="application/json", REMOTE_ADDR="192.0.2.15").status_code, 202)

    def test_public_form_accepts_real_csrf_token_and_rejects_files(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        token = client.get("/api/v1/session").json()["csrf_token"]
        data = {"email": "help@example.com", "subject": "Cannot sign in", "message": "Cannot open my account"}
        response = client.post("/api/v1/support/account-access", data, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 202)
        data["image"] = SimpleUploadedFile("private.jpg", b"private photo", content_type="image/jpeg")
        response = client.post("/api/v1/support/account-access", data, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 400)

    def test_admin_can_track_resolution_with_audit_reason(self):
        from types import SimpleNamespace
        from django.contrib import admin
        from django.test import RequestFactory
        from .models import AccountAccessRequest

        entry = AccountAccessRequest.objects.create(email="help@example.com", subject="Access help", message="Cannot open my account")
        operator = User.objects.create_superuser("access-operator@example.com", "strong-password")
        request = RequestFactory().post("/admin/operations/accountaccessrequest/")
        request.user = operator
        model_admin = admin.site._registry[AccountAccessRequest]
        fields = model_admin.get_form(request, entry).base_fields
        self.assertIn("status", fields)
        self.assertIn("operator_notes", fields)
        self.assertIn("audit_reason", fields)
        self.assertNotIn("email", fields)
        entry.status = AccountAccessRequest.Status.RESOLVED
        entry.operator_notes = "Reviewed account-access request"
        model_admin.save_model(request, entry, SimpleNamespace(cleaned_data={"audit_reason": "Access request reviewed"}), True)
        self.assertTrue(AuditEvent.objects.filter(actor=operator, object_id=entry.id, action="admin_updated").exists())

    @override_settings(AI_GATEWAY_MODE="fake")
    def test_operating_mode_does_not_claim_public_launch_readiness(self):
        mode = self.client.get("/api/v1/session").json()["operating_mode"]
        self.assertEqual(mode, {"synthetic_processing": True, "public_launch_ready": False})
        with override_settings(AI_GATEWAY_MODE="disabled"):
            self.assertFalse(self.client.get("/api/v1/session").json()["operating_mode"]["synthetic_processing"])


class SupportGrantTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = override_settings(MEDIA_ROOT=self.tempdir.name)
        self.settings.enable()

    def tearDown(self):
        self.settings.disable()
        self.tempdir.cleanup()

    def test_unassigned_grant_binds_first_mfa_operator_and_audits_view(self):
        owner = User.objects.create_user("owner@example.com", "strong-password", email_verified=True)
        operator = User.objects.create_superuser("operator@example.com", "strong-password")
        Authenticator.objects.create(user=operator, type=Authenticator.Type.TOTP, data={})
        offer = Offer.objects.create(version=1, name="Uji", price_idr=19900, active=True)
        template = TemplateVersion.objects.create(slug="support", version=1, name="Support", occasion="Test", people_count=2, description="Test", sample_asset="sample.jpg", configuration_hash="f" * 64, generation_config={"model": "test"})
        project = Project.objects.create(owner=owner, template=template, offer=offer, state=Project.State.ACTIVE)
        result = ResultVersion.objects.create(project=project, source_snapshot=[], region_snapshot=[], configuration_hash="f" * 64, kind=ResultVersion.Kind.CREATION, number=1, status=ResultVersion.Status.READY, expires_at=timezone.now() + timedelta(days=1))
        media = MediaAsset.objects.create(project=project, result=result, kind=MediaAsset.Kind.PREVIEW, file=SimpleUploadedFile("preview.jpg", b"private-image"), sha256="a" * 64, width=768, height=576, size_bytes=13, expires_at=result.expires_at)
        grant = SupportGrant.objects.create(owner=owner, project=project, purpose="Owner requested image review", expires_at=timezone.now() + timedelta(hours=1))
        self.client.force_login(operator)
        response = self.client.get(f"/api/v1/operator/projects/{project.id}/media/{media.id}")
        self.assertEqual(response.status_code, 200)
        grant.refresh_from_db()
        self.assertEqual(grant.staff, operator)
        self.assertTrue(AuditEvent.objects.filter(actor=operator, action="support_media_viewed", object_id=media.id).exists())
