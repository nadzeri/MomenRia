from types import SimpleNamespace
import os
import re
from urllib.parse import urlsplit
from urllib.parse import urlencode
from unittest.mock import patch
from uuid import uuid4
import subprocess
import sys

from django.contrib import admin
from django.core import mail
from django.test import Client, RequestFactory, TestCase, override_settings

from operations.models import AuditEvent

from .admin import UserAdmin
from .models import User


@override_settings(PUBLIC_ACCESS=False, ACCOUNT_RATE_LIMITS=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthenticationReturnTests(TestCase):
    def setUp(self):
        from catalog.models import FaceSlot, TemplateVersion

        self.template = TemplateVersion.objects.create(slug="return-context", version=1, name="Wisuda bersama keluarga", occasion="Wisuda", people_count=1, description="Test return destination", sample_asset="app/assets/home.webp", configuration_hash="test-return", generation_config={"scene": "test"})
        FaceSlot.objects.create(template=self.template, position=1, x="0.5", y="0.5")
        self.template.status = TemplateVersion.Status.PUBLISHED
        self.template.evidence_approved = True
        self.template.save()
        self.target = f"/#/studio/{self.template.pk}"

    def test_selected_template_is_visible_and_reciprocal_links_keep_next(self):
        query = urlencode({"next": self.target})
        login = self.client.get("/accounts/login/", {"next": self.target})
        signup = self.client.get("/accounts/signup/", {"next": self.target})
        for response in (login, signup):
            self.assertContains(response, f"Studio · {self.template.name}")
        self.assertContains(login, f'href="/accounts/signup/?{query}"')
        self.assertContains(signup, f'href="/accounts/login/?{query}"')

    def test_verification_reuses_pending_allauth_destination_and_returns_to_studio(self):
        from allauth.account.models import EmailAddress, EmailConfirmationHMAC

        response = self.client.post("/accounts/signup/", {"email": "chosen-template@example.com", "password1": "Family-portrait-2026!", "password2": "Family-portrait-2026!", "next": self.target}, follow=True)
        self.assertContains(response, f"Studio · {self.template.name}")
        self.assertContains(response, f'href="/accounts/login/?{urlencode({"next": self.target})}"')
        user = User.objects.get(email="chosen-template@example.com")
        confirmation = EmailConfirmationHMAC(EmailAddress.objects.get(user=user))
        page = self.client.get(f"/accounts/confirm-email/{confirmation.key}/")
        self.assertContains(page, f"Studio · {self.template.name}")
        self.assertRedirects(self.client.post(f"/accounts/confirm-email/{confirmation.key}/"), self.target, fetch_redirect_response=False)

    def test_external_and_malformed_destinations_never_lookup_templates(self):
        candidates = [f"https://outside.example/{self.target}", f"//outside.example/{self.target}", f"/\\outside.example/{self.target}", "/#/studio/not-a-uuid", f"/#/studio/{self.template.pk}?next=https://outside.example", f"/#/project/{uuid4()}"]
        with patch("accounts.context_processors.TemplateVersion.objects.filter") as lookup:
            for target in candidates:
                with self.subTest(target=target):
                    response = self.client.get("/accounts/login/", {"next": target})
                    self.assertNotContains(response, 'class="account-return"')
            lookup.assert_not_called()

    def test_pending_context_is_not_reused_for_new_or_expired_authentication(self):
        from allauth.account.models import EmailAddress, EmailConfirmationHMAC

        self.client.post("/accounts/signup/", {"email": "pending-context@example.com", "password1": "Family-portrait-2026!", "password2": "Family-portrait-2026!", "next": self.target})
        self.assertNotContains(self.client.get("/accounts/login/"), 'class="account-return"')
        self.assertNotContains(self.client.get("/accounts/confirm-email/", {"next": "https://outside.example/"}), 'class="account-return"')
        other = User.objects.create_user("different-context@example.com", "Family-portrait-2026!")
        different = EmailConfirmationHMAC(EmailAddress.objects.create(user=other, email=other.email, primary=True))
        self.assertNotContains(self.client.get(f"/accounts/confirm-email/{different.key}/"), 'class="account-return"')
        session = self.client.session
        session["account_login"]["initiated_at"] = 1
        session.save()
        self.assertNotContains(self.client.get("/accounts/confirm-email/"), 'class="account-return"')

    def test_only_public_templates_are_named_without_reading_project_details(self):
        from catalog.models import TemplateVersion

        with patch("projects.models.Project.objects.filter") as projects:
            response = self.client.get("/accounts/login/", {"next": f"{self.target}/{uuid4()}"})
            self.assertContains(response, self.template.name)
            projects.assert_not_called()
        TemplateVersion.objects.filter(pk=self.template.pk).update(status=TemplateVersion.Status.PAUSED)
        self.assertNotContains(self.client.get("/accounts/login/", {"next": self.target}), 'class="account-return"')

    def test_selected_studio_survives_forgot_password_through_completion(self):
        from allauth.account.models import EmailAddress

        user = User.objects.create_user("studio-recovery@example.com", "Family-portrait-2026!", email_verified=True)
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        query = urlencode({"next": self.target})
        receipt_next = f"/accounts/password/reset/done/?{query}"
        completion_next = f"/accounts/password/reset/key/done/?{query}"
        login = self.client.get("/accounts/login/", {"next": self.target})
        self.assertContains(login, f'href="/accounts/password/reset/?{query}"', count=1)
        reset = self.client.get(f"/accounts/password/reset/?{query}")
        self.assertContains(reset, self.template.name)
        self.assertContains(reset, f'name="next" value="{receipt_next}"')
        self.assertContains(reset, f'href="/accounts/login/?{query}"')
        invalid = self.client.post("/accounts/password/reset/", {"email": "invalid-email", "next": receipt_next})
        self.assertContains(invalid, self.template.name)
        self.assertTrue(invalid.context["form"].errors)
        receipt = self.client.post("/accounts/password/reset/", {"email": user.email, "next": receipt_next}, follow=True)
        self.assertContains(receipt, self.template.name)
        self.assertContains(receipt, "Kalau emailmu terdaftar")
        reset_url = re.search(r"https?://\S+", mail.outbox[-1].body).group()
        token = self.client.get(urlsplit(reset_url).path, follow=True)
        self.assertContains(token, self.template.name)
        self.assertContains(token, f'name="next" value="{completion_next}"')
        done = self.client.post(token.context["action_url"], {"password1": "Family-new-portrait-2026!", "password2": "Family-new-portrait-2026!", "next": completion_next}, follow=True)
        self.assertContains(done, self.template.name)
        self.assertContains(done, f'href="/accounts/login/?{query}">Masuk dengan kata sandi baru')
        self.client.get(f"/accounts/login/?{query}")
        self.assertRedirects(self.client.post("/accounts/login/", {"login": user.email, "password": "Family-new-portrait-2026!", "next": self.target}), self.target, fetch_redirect_response=False)

    def test_recovery_context_is_generic_but_bound_to_same_browser_and_token_account(self):
        from allauth.account.forms import default_token_generator
        from allauth.account.models import EmailAddress
        from allauth.account.utils import user_pk_to_url_str

        user = User.objects.create_user("receipt-owner@example.com", "Family-portrait-2026!", email_verified=True)
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        for email in (user.email, "unknown-context@example.com"):
            self.client.get("/accounts/password/reset/", {"next": self.target})
            receipt = self.client.post("/accounts/password/reset/", {"email": email, "next": f'/accounts/password/reset/done/?{urlencode({"next": self.target})}'}, follow=True)
            self.assertContains(receipt, "Kalau emailmu terdaftar")
            self.assertContains(receipt, self.template.name)
        other = User.objects.create_user("different-token@example.com", "Family-portrait-2026!")
        different_url = f"/accounts/password/reset/key/{user_pk_to_url_str(other)}-{default_token_generator.make_token(other)}/"
        response = self.client.get(different_url, follow=True)
        self.assertNotContains(response, 'class="account-return"')
        self.assertNotIn("account_recovery_return", self.client.session)
        self.client.get("/accounts/password/reset/", {"next": self.target})
        self.client.post("/accounts/password/reset/", {"email": user.email, "next": f'/accounts/password/reset/done/?{urlencode({"next": self.target})}'})
        reset_url = re.search(r"https?://\S+", mail.outbox[-1].body).group()
        self.assertNotContains(Client().get(urlsplit(reset_url).path, follow=True), 'class="account-return"')

    def test_recovery_context_expires_and_explicit_unsafe_next_clears_it(self):
        self.client.get("/accounts/password/reset/", {"next": self.target})
        session = self.client.session
        session["account_recovery_return"]["started_at"] = 1
        session.save()
        with patch("accounts.context_processors.TemplateVersion.objects.filter") as lookup:
            self.assertNotContains(self.client.get("/accounts/password/reset/done/"), 'class="account-return"')
            lookup.assert_not_called()
        self.assertNotIn("account_recovery_return", self.client.session)
        for target in ("https://outside.example/", "/#/studio/not-a-uuid"):
            self.client.get("/accounts/password/reset/", {"next": self.target})
            with patch("accounts.context_processors.TemplateVersion.objects.filter") as lookup:
                self.assertNotContains(self.client.get("/accounts/password/reset/done/", {"next": target}), 'class="account-return"')
                lookup.assert_not_called()
            self.assertNotIn("account_recovery_return", self.client.session)
        self.client.get("/accounts/password/reset/", {"next": self.target})
        self.client.get("/accounts/login/")
        self.assertNotIn("account_recovery_return", self.client.session)
        self.assertNotContains(self.client.get("/accounts/password/reset/done/"), 'class="account-return"')


class UserAdminAuditTests(TestCase):
    def test_account_queue_filters_and_exact_id_search(self):
        operator = User.objects.create_superuser("operator@example.com", "strong-password")
        target = User.objects.create_user("pending@example.com", "strong-password")
        User.objects.create_user("verified@example.com", "strong-password", email_verified=True)
        request = RequestFactory().get("/admin/accounts/user/", {"email_verified__exact": "0"})
        request.user = operator
        model_admin = UserAdmin(User, admin.site)
        self.assertEqual(list(model_admin.get_changelist_instance(request).queryset), [target])
        matches, duplicates = model_admin.get_search_results(request, User.objects.all(), str(target.pk))
        self.assertEqual(list(matches), [target])
        self.assertFalse(duplicates)

    def test_role_change_requires_reason_and_records_actor(self):
        operator = User.objects.create_superuser("operator@example.com", "strong-password")
        target = User.objects.create_user("target@example.com", "strong-password")
        request = RequestFactory().get("/admin/accounts/user/")
        request.user = operator
        model_admin = UserAdmin(User, admin.site)
        self.assertIn("audit_reason", model_admin.get_form(request, target).base_fields)
        target.is_staff = True
        model_admin.save_model(request, target, SimpleNamespace(cleaned_data={"audit_reason": "Approved support role"}), True)
        event = AuditEvent.objects.get(object_id=target.id, action="admin_updated")
        self.assertEqual(event.actor, operator)
        self.assertEqual(event.reason, "Approved support role")


class PublicAccessTests(TestCase):
    @override_settings(PAYMENT_PROVIDER="disabled", AI_GATEWAY_MODE="disabled")
    def test_launch_capabilities_are_explicit(self):
        payload = self.client.get("/api/v1/session").json()
        self.assertFalse(payload["capabilities"]["payments_enabled"])
        self.assertFalse(payload["capabilities"]["corrections_enabled"])

    @override_settings(PUBLIC_ACCESS=True, PUBLIC_OWNER_EMAIL="public-test@momenria.invalid")
    def test_customer_api_uses_shared_verified_owner_without_login(self):
        session = self.client.get("/api/v1/session")
        self.assertEqual(session.status_code, 200)
        self.assertIs(session.json().get("public_access"), True)
        self.assertEqual(self.client.get("/api/v1/projects").status_code, 200)
        owner = User.objects.get(email="public-test@momenria.invalid")
        self.assertTrue(owner.email_verified)
        self.assertFalse(owner.has_usable_password())
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    @override_settings(PUBLIC_ACCESS=True, PUBLIC_OWNER_EMAIL="public-test@momenria.invalid")
    def test_public_customer_api_ignores_existing_nonstaff_login(self):
        signed_in = User.objects.create_user("signed-in@example.com", "strong-password", email_verified=True)
        self.client.force_login(signed_in)
        session = self.client.get("/api/v1/session")
        self.assertEqual(session.json()["email"], "public-test@momenria.invalid")


class LaunchAccountTests(TestCase):
    @override_settings(PUBLIC_ACCESS=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_signup_sends_verification_and_confirmation_marks_customer_verified(self):
        from allauth.account.models import EmailAddress, EmailConfirmationHMAC

        response = self.client.post("/accounts/signup/", {"email": "new-family@example.com", "password1": "Family-portrait-2026!", "password2": "Family-portrait-2026!"})
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="new-family@example.com")
        self.assertFalse(user.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Verifikasi emailmu, yuk", mail.outbox[0].subject)
        self.assertIn("Kalau kamu nggak mendaftar", mail.outbox[0].body)
        self.assertContains(self.client.get(response.url), "Cek emailmu dulu, yuk")
        key = EmailConfirmationHMAC(EmailAddress.objects.get(user=user)).key
        self.assertContains(self.client.get(f"/accounts/confirm-email/{key}/"), "Ya, ini emailku")
        response = self.client.post(f"/accounts/confirm-email/{key}/")
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    @override_settings(PUBLIC_ACCESS=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_recovery_copy_keeps_reset_flow_working(self):
        from allauth.account.models import EmailAddress

        user = User.objects.create_user("recovery@example.com", "Portrait-before-2026!", email_verified=True)
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        response = self.client.post("/accounts/password/reset/", {"email": user.email}, follow=True)
        self.assertContains(response, "Cek inboxmu, ya")
        self.assertIn("Link untuk ganti kata sandimu", mail.outbox[-1].subject)
        self.assertIn("Kalau kamu nggak meminta reset", mail.outbox[-1].body)
        reset_url = re.search(r"https?://\S+", mail.outbox[-1].body).group()
        response = self.client.get(urlsplit(reset_url).path, follow=True)
        self.assertContains(response, "Buat kata sandi baru")
        response = self.client.post(response.context["action_url"], {"password1": "Portrait-after-2026!", "password2": "Portrait-after-2026!"}, follow=True)
        self.assertContains(response, "Kata sandimu sudah diganti")
        self.assertContains(response, 'href="/accounts/login/">Masuk dengan kata sandi baru')
        user.refresh_from_db()
        self.assertTrue(user.check_password("Portrait-after-2026!"))
        self.client.force_login(user)
        self.assertContains(self.client.get("/accounts/email/"), "Email akunmu")
        self.assertContains(self.client.get("/accounts/password/change/"), "Buat kata sandi baru")
        self.assertContains(self.client.get("/accounts/logout/"), "Mau keluar dulu?")

    @override_settings(PUBLIC_ACCESS=False, ACCOUNT_RATE_LIMITS=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_unverified_recovery_is_public_and_repeat_login_resends(self):
        from allauth.account.models import EmailAddress

        user = User.objects.create_user("pending@example.com", "Family-portrait-2026!")
        EmailAddress.objects.create(user=user, email=user.email, primary=True)
        sent_page = self.client.get("/accounts/confirm-email/")
        self.assertContains(sent_page, "Masuk untuk kirim ulang verifikasi")
        self.assertContains(sent_page, 'href="/#/support"')
        self.assertContains(sent_page, "Daftar dengan email yang benar")
        response = self.client.post("/accounts/login/", {"login": user.email, "password": "Family-portrait-2026!", "next": "/#/templates"}, follow=True)
        self.assertContains(response, "Cek emailmu dulu, yuk")
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post("/accounts/login/", {"login": user.email, "password": "Family-portrait-2026!"}, follow=True)
        self.assertEqual(len(mail.outbox), 2)
        self.assertContains(response, "Cek emailmu dulu, yuk")

    @override_settings(PUBLIC_ACCESS=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_verification_resend_keeps_allauth_cooldown_and_invalid_link_recovery(self):
        from allauth.account.models import EmailAddress

        user = User.objects.create_user("cooldown@example.com", "Family-portrait-2026!")
        EmailAddress.objects.create(user=user, email=user.email, primary=True)
        for _ in range(2):
            response = self.client.post("/accounts/login/", {"login": user.email, "password": "Family-portrait-2026!"}, follow=True)
            self.assertContains(response, "Cek emailmu dulu, yuk")
        self.assertEqual(len(mail.outbox), 1)
        invalid = self.client.get("/accounts/confirm-email/invalid-key/")
        self.assertContains(invalid, "Masuk untuk minta verifikasi baru")
        self.assertContains(invalid, 'href="/#/support"')

    @override_settings(PUBLIC_ACCESS=False, ACCOUNT_RATE_LIMITS=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_unknown_reset_email_has_same_generic_receipt_and_public_help(self):
        from allauth.account.models import EmailAddress

        user = User.objects.create_user("known@example.com", "Family-portrait-2026!", email_verified=True)
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        known = self.client.post("/accounts/password/reset/", {"email": user.email}, follow=True)
        unknown = self.client.post("/accounts/password/reset/", {"email": "unknown@example.com"}, follow=True)
        for response in (known, unknown):
            self.assertContains(response, "Kalau emailmu terdaftar")
            self.assertContains(response, "Minta bantuan akses akun")
            self.assertContains(response, 'href="/#/support"')

    @override_settings(PUBLIC_ACCESS=False)
    def test_login_has_one_reset_link_and_preserves_return_destination(self):
        response = self.client.get("/accounts/login/", {"next": "/#/templates/example"})
        self.assertContains(response, 'href="/accounts/password/reset/"', count=1)
        self.assertContains(response, "Lupa kata sandi?", count=1)
        self.assertContains(response, 'name="next" value="/#/templates/example"')

    @override_settings(PUBLIC_ACCESS=False, ACCOUNT_RATE_LIMITS=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_actions_are_contextual_and_keep_allauth_validation(self):
        from allauth.account.models import EmailAddress

        user = User.objects.create_user("primary@example.com", "Family-portrait-2026!", email_verified=True)
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        alternate = EmailAddress.objects.create(user=user, email="alternate@example.com", verified=True)
        pending = EmailAddress.objects.create(user=user, email="pending@example.com")
        self.client.force_login(user)
        response = self.client.get("/accounts/email/")
        self.assertContains(response, 'href="/accounts/email/" aria-current="page"')
        self.assertContains(response, 'href="/#/projects"')
        self.assertNotContains(response, "auth-story")
        self.assertContains(response, 'name="action_primary"', count=1)
        self.assertContains(response, 'name="action_send"', count=1)
        self.assertContains(response, 'name="action_remove"', count=2)
        self.client.post("/accounts/email/", {"email": pending.email, "action_primary": ""})
        pending.refresh_from_db()
        self.assertFalse(pending.primary)
        self.client.post("/accounts/email/", {"email": pending.email, "action_send": ""})
        self.assertEqual(len(mail.outbox), 1)
        self.client.post("/accounts/email/", {"email": alternate.email, "action_primary": ""})
        alternate.refresh_from_db()
        self.assertTrue(alternate.primary)
        self.client.post("/accounts/email/", {"email": pending.email, "action_remove": ""})
        self.assertFalse(EmailAddress.objects.filter(pk=pending.pk).exists())
        response = self.client.post("/accounts/email/", {"email": "bad-email", "action_add": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        other = User.objects.create_user("other@example.com", "Family-portrait-2026!", email_verified=True)
        other_email = EmailAddress.objects.create(user=other, email=other.email, primary=True, verified=True)
        self.client.post("/accounts/email/", {"email": other.email, "action_remove": ""})
        self.assertTrue(EmailAddress.objects.filter(pk=other_email.pk).exists())
        protected_client = Client(enforce_csrf_checks=True)
        protected_client.force_login(user)
        self.assertEqual(protected_client.post("/accounts/email/", {"email": alternate.email, "action_remove": ""}).status_code, 403)

    @override_settings(PUBLIC_ACCESS=False)
    def test_mfa_account_shell_and_admin_enrollment_gate(self):
        from allauth.mfa.models import Authenticator

        operator = User.objects.create_superuser("operator@example.com", "Family-portrait-2026!")
        self.client.force_login(operator)
        self.assertRedirects(self.client.get("/admin/accounts/user/"), "/accounts/2fa/", fetch_redirect_response=False)
        response = self.client.get("/accounts/2fa/")
        self.assertContains(response, 'href="/accounts/2fa/" aria-current="page"')
        self.assertNotContains(response, "auth-story")
        Authenticator.objects.create(user=operator, type=Authenticator.Type.TOTP, data={"secret": "test-enrollment-only"})
        response = self.client.get("/accounts/2fa/")
        self.assertContains(response, 'class="account-button account-danger"')
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 200)
        self.assertRedirects(self.client.post("/admin/accounts/user/", {}), "/accounts/reauthenticate/?next=%2Fadmin%2Faccounts%2Fuser%2F", fetch_redirect_response=False)

    def test_production_rejects_shared_owner_mode(self):
        result = subprocess.run([sys.executable, "-c", "import momenria.settings"], env={**os.environ, "APP_ENV": "production", "PUBLIC_ACCESS": "true", "DJANGO_SECRET_KEY": "test-guard-only", "DATABASE_URL": "postgresql://test:test@localhost/test"}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production requires PUBLIC_ACCESS=false", result.stderr)
