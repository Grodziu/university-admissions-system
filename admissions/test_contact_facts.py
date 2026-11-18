"""Regression of the physical 6NF decomposition and the writable compatibility view."""
from concurrent.futures import ThreadPoolExecutor
from django.db import connection, connections, transaction, IntegrityError
from django.test import TestCase, TransactionTestCase
from .models import (User, CandidateContact, ContactAnchor, CandidatePhone,
                     CandidatePortfolio, CandidateNotificationAddress)


class ContactFactsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='facts@example.com', email='facts@example.com')

    def test_create_update_delete_and_optional_facts(self):
        contact = CandidateContact.objects.create(user=self.user, phone='123456789',
            portfolio_url='https://example.com/work', notification_email='news@example.com')
        self.assertEqual(CandidatePhone.objects.get(contact_id=self.user.pk).value, '123456789')
        self.assertEqual(CandidatePortfolio.objects.get(contact_id=self.user.pk).value, contact.portfolio_url)
        self.assertEqual(CandidateNotificationAddress.objects.get(contact_id=self.user.pk).value, contact.notification_email)
        contact, created = CandidateContact.objects.update_or_create(user=self.user,
            defaults={'phone': '987654321', 'portfolio_url': ''})
        self.assertFalse(created)
        self.assertEqual(contact.notification_email, 'news@example.com')
        self.assertFalse(CandidatePortfolio.objects.exists())
        self.assertEqual(CandidatePhone.objects.get().value, '987654321')
        CandidateContact.objects.filter(user=self.user).delete()
        self.assertFalse(ContactAnchor.objects.exists())
        self.assertFalse(CandidatePhone.objects.exists())
        self.assertFalse(CandidateNotificationAddress.objects.exists())

    def test_empty_contact_retains_identity_without_empty_or_null_facts(self):
        CandidateContact.objects.create(user=self.user)
        self.assertTrue(ContactAnchor.objects.filter(user=self.user).exists())
        self.assertEqual(CandidateContact.objects.get(user=self.user).phone, '')
        self.assertFalse(CandidatePhone.objects.exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            CandidatePhone.objects.create(contact_id=self.user.pk, value='')

    def test_duplicate_owner_and_rollbacks_preserve_the_three_facts(self):
        CandidateContact.objects.create(user=self.user, phone='123456789')
        with self.assertRaises(IntegrityError), transaction.atomic():
            CandidateContact.objects.create(user=self.user, phone='999999999')
        with self.assertRaises(RuntimeError), transaction.atomic():
            CandidateContact.objects.filter(user=self.user).update(notification_email='news@example.com')
            raise RuntimeError('cancel')
        self.assertEqual(CandidateContact.objects.get(user=self.user).phone, '123456789')
        self.assertFalse(CandidateNotificationAddress.objects.exists())

    def test_user_cascade_and_for_update_support(self):
        CandidateContact.objects.create(user=self.user, phone='123456789')
        with transaction.atomic():
            self.assertEqual(CandidateContact.objects.select_for_update().get(user=self.user).phone, '123456789')
        self.user.delete()
        self.assertFalse(CandidateContact.objects.exists())
        self.assertFalse(ContactAnchor.objects.exists())

    def test_bulk_contacts_work_through_the_view_as_application_role(self):
        from django.db import ProgrammingError
        with connection.cursor() as cursor:
            cursor.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON admissions_candidatecontact TO pk_app')
            cursor.execute('REVOKE INSERT,UPDATE,DELETE ON admissions_contactanchor,admissions_candidatephone FROM pk_app')
            cursor.execute('SET LOCAL ROLE pk_app')
        try:
            CandidateContact.objects.bulk_create([CandidateContact(user_id=self.user.pk, phone='123456789')])
            self.assertEqual(CandidateContact.objects.get(user_id=self.user.pk).phone, '123456789')
            with self.assertRaises(ProgrammingError), transaction.atomic():
                CandidatePhone.objects.filter(contact_id=self.user.pk).update(value='987654321')
        finally:
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')


class ContactConcurrentTests(TransactionTestCase):
    def test_independent_field_updates_do_not_erase_each_other(self):
        user = User.objects.create_user(username='parallel@example.com', email='parallel@example.com')
        CandidateContact.objects.create(user=user, phone='123456789')

        def change(field, value):
            try:
                with transaction.atomic():
                    CandidateContact.objects.filter(user_id=user.pk).update(**{field: value})
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda pair: change(*pair), [
                ('portfolio_url', 'https://example.com/work'), ('notification_email', 'news@example.com')]))
        contact = CandidateContact.objects.get(user=user)
        self.assertEqual(contact.portfolio_url, 'https://example.com/work')
        self.assertEqual(contact.notification_email, 'news@example.com')
