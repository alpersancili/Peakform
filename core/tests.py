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

    def test_landing_page_shows_real_community_posts_not_placeholders(self):
        from django.contrib.auth.models import User

        from community.models import Post

        user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        Post.objects.create(author=user, body="A real community post")
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "A real community post")
        self.assertNotContains(response, "Mia R.")


class LegalPageTests(TestCase):
    def test_privacy_page_loads(self):
        response = self.client.get(reverse("core:privacy"))
        self.assertEqual(response.status_code, 200)

    def test_terms_page_loads(self):
        response = self.client.get(reverse("core:terms"))
        self.assertEqual(response.status_code, 200)

    def test_footer_links_to_real_pages(self):
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, reverse("core:privacy"))
        self.assertContains(response, reverse("core:terms"))
