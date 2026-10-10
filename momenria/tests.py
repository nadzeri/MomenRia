from django.test import TestCase, override_settings


@override_settings(PUBLIC_ACCESS=False, PAYMENT_PROVIDER="disabled")
class PublicPolicyTests(TestCase):
    def test_policies_are_public_without_javascript(self):
        for path, heading in (
            ("/terms/", "Syarat dan Ketentuan"),
            ("/privacy/", "Kebijakan Privasi"),
            ("/refunds/", "Kebijakan Pengembalian Dana"),
            ("/contact/", "Hubungi Kami"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, heading, status_code=200)
                self.assertContains(response, 'href="/refunds/"')
                self.assertContains(response, 'href="/contact/"')
                self.assertContains(response, 'href="mailto:support@momenria.id"')

    def test_terms_disclose_lifetime_pricing_and_equal_quality(self):
        response = self.client.get("/terms/")
        for text in ("3 foto", "seumur hidup", "Rp9.900", "koreksi", "tanpa watermark"):
            self.assertIn(text.lower(), response.content.decode().lower())

    def test_contact_has_real_callable_phone(self):
        response = self.client.get("/contact/")
        self.assertContains(response, 'href="tel:+6282226669926"')

    def test_app_has_policy_links_if_catalog_is_unavailable(self):
        response = self.client.get("/")
        for path in ("/terms/", "/privacy/", "/refunds/", "/contact/"):
            self.assertContains(response, f'href="{path}"')
