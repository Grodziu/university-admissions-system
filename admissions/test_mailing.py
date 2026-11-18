from datetime import date, datetime, timezone as utc
from smtplib import SMTPServerDisconnected
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from . import mailing, services
from .models import CandidateContact, EmailDelivery
from .tests import Fixture


@override_settings(PK_MAIL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   DEFAULT_FROM_EMAIL='rekrutacja@example.com')
class NotificationDeliveryTests(Fixture, TestCase):
    def setUp(self):
        self.setup_data()
        self.contact = CandidateContact.objects.get(user=self.candidate)

    def save_address(self, email):
        return self.client.post('/api/action', {
            'action': 'profile', 'first_name': self.candidate.first_name,
            'last_name': self.candidate.last_name, 'notification_email': email,
        }, format='json')

    def test_published_result_sends_an_email_and_keeps_in_app_notification(self):
        self.assertEqual(self.save_address('zly-adres').status_code, 400)
        self.assertEqual(self.save_address('powiadomienia@example.com').status_code, 200)
        self.application()
        self.close_submissions()
        services.publish(self.commission, self.offers['I'].id)
        workspace = self.client.get('/api/workspace').json()
        self.assertEqual(workspace['profile']['notification_email'], 'powiadomienia@example.com')
        self.assertEqual(workspace['user']['email'], self.candidate.email)
        self.assertEqual(workspace['unread_notifications'], 1)
        self.assertTrue(mailing.deliver_next())
        self.assertFalse(mailing.deliver_next())
        self.assertEqual(mail.outbox[0].to, ['powiadomienia@example.com'])
        self.assertIn('Opublikowano wyniki', mail.outbox[0].subject)
        self.assertEqual(EmailDelivery.objects.get().state, EmailDelivery.State.SENT)
        self.client.post('/api/action', {'action': 'read_notifications'}, format='json')
        self.assertEqual(self.client.get('/api/workspace').json()['unread_notifications'], 0)

    def test_delivery_can_retry_and_respects_new_address_preference(self):
        self.contact.notification_email = 'poprzedni@example.com'
        self.contact.save(update_fields=['notification_email'])
        services.notify(self.candidate, 'Przyjęto zgłoszenie', 'Dane w aplikacji.')
        with patch('admissions.mailing.send_mail', side_effect=SMTPServerDisconnected):
            self.assertTrue(mailing.deliver_next())
        delivery = EmailDelivery.objects.get()
        self.assertEqual(delivery.attempts, 1)
        self.assertGreater(delivery.available_at, timezone.now())
        self.assertEqual(self.candidate.notifications.count(), 1)
        self.contact.notification_email = ''
        self.contact.save(update_fields=['notification_email'])
        EmailDelivery.objects.update(available_at=timezone.now())
        self.assertTrue(mailing.deliver_next())
        delivery.refresh_from_db()
        self.assertEqual(delivery.state, EmailDelivery.State.CANCELLED)

    def test_card_policy_uses_october_of_the_campaign_year(self):
        campaign = SimpleNamespace(start=datetime(2027, 6, 1, 8, tzinfo=utc.utc))
        self.assertEqual(services.student_card_period(campaign), (date(2027, 10, 1), date(2028, 3, 31)))
