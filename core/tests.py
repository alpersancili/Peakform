from django.test import TestCase
from django.urls import reverse


class LandingPageTests(TestCase):
    def test_landing_page_loads(self):
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Peakform")

    def test_landing_page_uses_expected_template(self):
        response = self.client.get(reverse("core:landing"))
        self.assertTemplateUsed(response, "core/landing.html")
        self.assertTemplateUsed(response, "base.html")
