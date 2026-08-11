"""Tests for the frontend demo UI."""

from django.test import Client, TestCase
from django.urls import reverse


class FrontendIndexTest(TestCase):
    """Verify the demo frontend page loads."""

    def setUp(self):
        self.client = Client()

    def test_index_page_returns_200(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_index_uses_correct_template(self):
        response = self.client.get(reverse("home"))
        self.assertTemplateUsed(response, "frontend/index.html")

    def test_index_contains_html_structure(self):
        response = self.client.get("/")
        self.assertContains(response, "<html", status_code=200)
