from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from .models import ContactMessage

class ContactMessageApiTests(TestCase):
    def test_health_check_get(self):
        url = reverse('contact_message')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("online", response.data.get("status", ""))

    def test_missing_fields_validation(self):
        url = reverse('contact_message')
        response = self.client.post(url, {}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data.get("success"))
        self.assertIn("errors", response.data)

    def test_invalid_email_validation(self):
        url = reverse('contact_message')
        response = self.client.post(url, {
            "name": "Test User",
            "email": "not-an-email",
            "subject": "Test Subject",
            "message": "Test Message"
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data.get("errors", {}))

    @patch('api.views.EmailMessage.send')
    def test_successful_contact_submission(self, mock_send):
        mock_send.return_value = 1
        url = reverse('contact_message')
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "subject": "Python Training Opportunity",
            "message": "We would like to hire you for our upcoming Django training program."
        }
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data.get("success"))

        # Verify DB entry
        message_in_db = ContactMessage.objects.filter(email="jane@example.com").first()
        self.assertIsNotNone(message_in_db)
        self.assertEqual(message_in_db.name, "Jane Doe")
        self.assertTrue(message_in_db.email_sent)
        self.assertTrue(mock_send.called)
