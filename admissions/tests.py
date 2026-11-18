"""Acceptance and regression tests use PostgreSQL, including its triggers."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
import hashlib
import io
from functools import wraps
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections, close_old_connections, transaction, DatabaseError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import *
from .domain import BachelorStrategy, MasterStrategy, PostgraduateStrategy, Result, RuleError, select_with_ties
from . import services


def fixed_totp(test):
    """Keep the 30-second step fixed while expensive password hashing runs."""
    @wraps(test)
    def run(*args, **kwargs):
        import pyotp
        from datetime import datetime
        moment = 1800000010
        verify = pyotp.TOTP.verify
        with patch('admissions.api.time.time', return_value=moment), \
             patch.object(pyotp.TOTP, 'now', lambda self: self.at(moment)), \
             patch.object(pyotp.TOTP, 'verify', lambda self, otp, for_time=None, valid_window=0: verify(self, otp, datetime.fromtimestamp(moment), valid_window)):
            return test(*args, **kwargs)
    return run


class DomainTests(TestCase):
    def test_wr_cap_and_bonus(self):
        policy = BachelorStrategy()
        self.assertEqual(policy.calculate({'M': 100, 'P1': 95, 'P2': 95, 'bonus_approved': True}).score, Decimal(1000))
        self.assertEqual(policy.calculate({'M': 0, 'P1': 0, 'P2': 0}).score, Decimal(0))
        self.assertEqual(policy.calculate({'M': 90, 'P1': 88, 'P2': 74}).score, Decimal(856))

    def test_portfolio_changes_only_weaker_weighted_component(self):
        result = BachelorStrategy().calculate({'M': 50, 'P1': 40, 'P2': 80, 'excellent_portfolio': True})
        self.assertEqual(result.score, Decimal(780))
        self.assertEqual(result.explanation['P1'], '80')
        self.assertEqual(result.explanation['P2'], '100')
        self.assertEqual(result.explanation['P2_before_portfolio'], '40')

    def test_master_only_average(self):
        result = MasterStrategy().calculate({'average': '4.56', 'M': 100, 'P1': 100, 'bonus_approved': True})
        self.assertEqual(result.score, Decimal('4.56'))

    def test_invalid_numbers_rejected(self):
        for value in ['NaN', 'Infinity', -1, 101, '90.001', 'x', None]:
            with self.subTest(value=value), self.assertRaises(RuleError):
                BachelorStrategy().calculate({'M': value, 'P1': 80, 'P2': 70})
        for value in ['1.99', '5.01', 'NaN']:
            with self.assertRaises(RuleError):
                MasterStrategy().calculate({'average': value})

    def test_tie_overflow(self):
        rows = [(i, Result(Decimal(score), {}), timezone.now()) for i, score in [(1, 900), (2, 800), (3, 800), (4, 700)]]
        ordered, admitted = select_with_ties(rows, 2, 'I')
        self.assertEqual(admitted, {1, 2, 3})
        self.assertEqual(select_with_ties(rows, 0, 'I')[1], set())

    def test_postgraduate_chronology_and_diploma(self):
        now = timezone.now()
        rows = [(1, Result(None, {}), now), (2, Result(None, {}), now - timedelta(seconds=1))]
        self.assertEqual(select_with_ties(rows, 1, 'PG')[1], {2})
        self.assertIsNone(PostgraduateStrategy().calculate({'diploma': 'licencjat'}).score)
        with self.assertRaises(RuleError):
            PostgraduateStrategy().calculate({})


class Fixture:
    def setup_data(self):
        self.now = timezone.now()
        self.campaign = Campaign.objects.create(name='Test', start=self.now - timedelta(days=1), end=self.now + timedelta(days=59), demo_clock=self.now)
        for degree, count, length in [('I', 3, 20), ('II', 2, 30), ('PG', 2, 30)]:
            for i in range(count):
                end = self.campaign.start + timedelta(days=length * (i + 1))
                Round.objects.create(campaign=self.campaign, degree=degree, number=i + 1,
                    start=self.campaign.start + timedelta(days=length * i), application_end=end - timedelta(days=5), end=end)
        self.faculty = Faculty.objects.create(code='WIiM', name='Test', color='#77A43F')
        self.program = Program.objects.create(name='Informatyka', faculty=self.faculty, description='Test')
        self.offers = {}
        for degree in ['I', 'II', 'PG']:
            self.offers[degree] = Offer.objects.create(campaign=self.campaign, program=self.program, degree=degree,
                mode='N' if degree == 'PG' else 'S', capacity=3, minimum=2, fee=85)
            AllowedSubject.objects.create(offer=self.offers[degree], subject='informatyka')
        self.commission = User.objects.create_user(username='commission@test.local', email='commission@test.local', password='Testing-pass-983', role='commission')
        self.admin = User.objects.create_user(username='admin@test.local', email='admin@test.local', password='Testing-pass-983', role='admin')
        self.candidate = self.person(0)
        self.client = APIClient()
        self.client.force_authenticate(self.candidate)

    def person(self, i):
        from .identity import demo_pesel
        from .profiles import demo_residence
        p = User.objects.create_user(username=f'person{i}@test.local', email=f'person{i}@test.local', password='Testing-pass-983', first_name='Anna', last_name=str(i))
        CandidateIdentity.objects.create(user=p, pesel=demo_pesel(p.pk))
        CandidateContact.objects.create(user=p, phone='000000000')
        Residence.objects.create(user=p, **demo_residence(i))
        ExamResult.objects.create(user=p, subject='matematyka', level='basic', value=90)
        ExamResult.objects.create(user=p, subject='informatyka', level='extended', value=80)
        AcademicAverage.objects.create(user=p, value='4.50')
        Diploma.objects.create(user=p, title='inżynier')
        return p

    def application(self, person=None, degree='I', score=80, status='verified'):
        person = person or self.candidate
        o = self.offers[degree]
        app = Application.objects.create(candidate=person, offer=o, round=Round.objects.get(campaign=self.campaign, degree=degree, number=1),
            status=status, submitted_at=timezone.now(), payment_approved=status == 'verified', payment_amount=85 if status == 'verified' else None,
            input_snapshot={'M': '90', 'P1': str(score), 'P2': '50', 'average': str(score) if degree == 'II' else '4.5', 'diploma': 'inżynier'})
        for kind in ['education', 'fee']:
            Document.objects.create(application=app, kind=kind, revision=1, file='test/missing.pdf', original_name='test.pdf', sha256='0' * 64)
        return app

    def close_submissions(self, degree='I'):
        round_ = Round.objects.get(campaign=self.campaign, degree=degree, number=1)
        self.campaign.demo_clock = round_.application_end
        self.campaign.save()
        return round_


class WorkflowTests(Fixture, TestCase):
    def setUp(self):
        self.setup_data()

    def test_20_30_day_rounds_share_end(self):
        self.assertEqual(Round.objects.filter(degree='I').count(), 3)
        self.assertEqual(Round.objects.filter(degree='II').count(), 2)
        self.assertEqual(Round.objects.filter(degree='PG').count(), 2)
        ends = [Round.objects.filter(degree=d).order_by('-number').first().end for d in ['I', 'II', 'PG']]
        self.assertEqual(len(set(ends)), 1)

    def test_draft_idempotency_and_profile_snapshot(self):
        a = services.create_application(self.candidate, self.offers['I'].id)
        self.assertEqual(a.id, services.create_application(self.candidate, self.offers['I'].id).id)
        for k in ['education', 'fee']:
            Document.objects.create(application=a, kind=k, revision=1, file='test.pdf', original_name='test.pdf', sha256='x' * 64)
        services.submit(self.candidate, a.id)
        ExamResult.objects.filter(user=self.candidate, level='basic').update(value=10)
        a.refresh_from_db()
        self.assertEqual(a.input_snapshot['M'], '90.00')
        first_time = a.submitted_at
        services.submit(self.candidate, a.id)
        a.refresh_from_db()
        self.assertEqual(first_time, a.submitted_at)

    def test_required_documents_and_fee_review(self):
        a = services.create_application(self.candidate, self.offers['I'].id)
        with self.assertRaises(ValidationError):
            services.submit(self.candidate, a.id)
        a = self.application(self.person(1), status='submitted')
        with self.assertRaises(ValidationError):
            services.review(self.commission, a.id, {'decision': 'verify', 'payment_amount': 84})
        services.review(self.commission, a.id, {'decision': 'verify', 'payment_amount': 85})
        a.refresh_from_db()
        self.assertTrue(a.payment_approved)
        self.assertEqual(a.status, 'verified')

    def test_publish_ties_and_immutable_history(self):
        apps = [self.application(self.person(i), score=score) for i, score in enumerate([95, 90, 80, 80, 70], 1)]
        self.close_submissions()
        pub = services.publish(self.commission, self.offers['I'].id)
        self.assertEqual(pub.qualified_count, 4)
        self.assertEqual(pub.overflow, 1)
        self.assertEqual(pub.id, services.publish(self.commission, self.offers['I'].id).id)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Publication.objects.filter(pk=pub.pk).update(cutoff=1)
        old_score = pub.entries.get(application=apps[-1]).score
        new = services.publish(self.commission, self.offers['I'].id, 'Sprostowanie wyniku z dokumentu', {'application_id': apps[-1].id, 'P1': 99})
        self.assertEqual(new.version, 2)
        self.assertEqual(pub.entries.get(application=apps[-1]).score, old_score)
        self.assertEqual(new.entries.get(application=apps[-1]).rank, 1)

    def test_master_ranking_same_average_same_rank(self):
        self.offers['II'].capacity = self.offers['II'].minimum = 1
        self.offers['II'].save()
        for i in [1, 2]:
            self.application(self.person(i), degree='II', score='4.60')
        self.close_submissions('II')
        pub = services.publish(self.commission, self.offers['II'].id)
        self.assertEqual(pub.qualified_count, 2)
        self.assertEqual(pub.cutoff, Decimal('4.60'))
        self.assertEqual(set(pub.entries.values_list('rank', flat=True)), {1})

    def test_postgraduate_order_not_review_order(self):
        self.offers['PG'].capacity = self.offers['PG'].minimum = 1
        self.offers['PG'].save()
        first = self.application(self.person(1), degree='PG')
        second = self.application(self.person(2), degree='PG')
        self.close_submissions('PG')
        pub = services.publish(self.commission, self.offers['PG'].id)
        self.assertEqual(pub.entries.get(decision='qualified').application_id, first.id)
        self.assertIsNone(pub.cutoff)
        self.assertEqual(pub.entries.get(application=second).decision, 'waitlist')

    def test_deadline_and_pending_review_block(self):
        app = self.application(status='submitted')
        with self.assertRaises(ValidationError):
            services.publish(self.commission, self.offers['I'].id)
        r = self.close_submissions()
        with self.assertRaises(ValidationError):
            services.publish(self.commission, self.offers['I'].id)
        with self.assertRaises(ValidationError):
            services.move_clock(self.admin, self.campaign.id, r.end)
        services.review(self.commission, app.id, {'decision': 'reject', 'feedback': 'Brak zgodności dokumentu.'})
        with self.assertRaisesMessage(ValidationError, 'Brak zweryfikowanych'):
            services.publish(self.commission, self.offers['I'].id)
        services.move_clock(self.admin, self.campaign.id, r.end)

    def test_confirmation_expiration_and_resubmission(self):
        a = self.application()
        r = self.close_submissions()
        services.publish(self.commission, self.offers['I'].id)
        services.move_clock(self.admin, self.campaign.id, r.end)
        a.refresh_from_db()
        self.assertEqual(a.status, 'expired')
        with self.assertRaises(ValidationError):
            services.candidate_decision(self.candidate, a.id, 'confirm')
        services.candidate_decision(self.candidate, a.id, 'continue')
        a.refresh_from_db()
        self.assertEqual(a.round.number, 2)
        self.assertEqual(a.status, 'draft')

    def test_final_thresholds_and_minimum(self):
        for i in [1, 2]:
            self.application(self.person(i), status='confirmed')
        self.campaign.demo_clock = self.campaign.end
        self.campaign.save()
        services.finalize(self.commission, self.campaign.id)
        self.offers['I'].refresh_from_db()
        self.offers['II'].refresh_from_db()
        self.assertEqual(self.offers['I'].state, 'launched')
        self.assertEqual(self.offers['II'].state, 'canceled')
        anon = APIClient()
        rows = anon.get('/api/thresholds').json()
        canceled = next(r for r in rows if r['degree'] == 'II')
        self.assertEqual({v['label'] for v in canceled['values']}, {'nie uruchomiono'})

    def test_warning_only_second_round_for_both_degrees(self):
        from .api import offer_data
        for degree in ['I', 'II']:
            self.assertFalse(offer_data(self.offers[degree], {}, set())['threatened'])
            r = Round.objects.get(campaign=self.campaign, degree=degree, number=2)
            self.offers[degree].campaign.demo_clock = r.start
            self.assertTrue(offer_data(self.offers[degree], {}, set())['threatened'])
            self.offers[degree].campaign.demo_clock = self.now

    def test_candidate_cannot_read_or_change_other_application(self):
        other = self.application(self.person(2))
        doc = other.documents.first()
        self.assertEqual(self.client.get(f'/api/document/{doc.id}').status_code, 403)
        self.assertEqual(self.client.get(f'/api/history/{other.id}').status_code, 403)
        self.assertEqual(self.client.post('/api/action', {'action': 'withdraw', 'id': other.id}, format='json').status_code, 403)
        self.assertEqual(self.client.post('/api/action', {'action': 'publish', 'offer_id': self.offers['I'].id}, format='json').status_code, 403)
        self.assertEqual(self.client.get('/api/export').status_code, 403)
        self.assertEqual(self.client.post('/api/backup').status_code, 403)

    def test_upload_validation_rejects_disguised_executable(self):
        a = services.create_application(self.candidate, self.offers['I'].id)
        file = SimpleUploadedFile('proof.pdf', b'MZ not a PDF', content_type='application/pdf')
        self.assertEqual(self.client.post(f'/api/upload/{a.id}', {'kind': 'fee', 'file': file}, format='multipart').status_code, 400)
        self.assertFalse(a.documents.exists())

    def test_database_guard_and_materialized_counts(self):
        a = self.application()
        with connection.cursor() as cursor:
            cursor.execute('SELECT applications,verified,confirmed FROM pk_offer_stats WHERE offer_id=%s', [a.offer_id])
            self.assertEqual(cursor.fetchone(), (1, 1, 0))
            cursor.execute('SELECT count(*) FROM pk_row_audit WHERE application_id=%s', [a.id])
            self.assertGreater(cursor.fetchone()[0], 0)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Application.objects.filter(pk=a.pk).update(round=Round.objects.get(degree='II', number=1))
        with self.assertRaises(DatabaseError), transaction.atomic():
            Application.objects.filter(pk=a.pk).update(payment_amount=84)

    def test_sql_and_python_wr_agree(self):
        with connection.cursor() as cursor:
            for values in [(0,0,0,0), (100,95,95,50), (90,88,74,0), (80,80,100,0)]:
                cursor.execute('SELECT pk_wr(%s,%s,%s,%s)', values)
                expected = min(1000, 2*values[0]+6*values[1]+2*values[2]+values[3])
                self.assertEqual(cursor.fetchone()[0], Decimal(expected))

    def test_register_recover_revokes_old_session(self):
        client = APIClient()
        from .identity import demo_pesel
        body = {'email': 'new@test.local', 'password': 'Fresh-secret-123', 'first_name': 'Jan', 'last_name': 'Test',
                'pesel': demo_pesel(190000), 'phone': '000000000',
                'address': {'city': 'Kraków', 'building': '24', 'street': 'Warszawska', 'postal_code': '31-155'}}
        for missing in ['pesel', 'phone', 'address']:
            self.assertEqual(client.post('/api/register', {k: v for k, v in body.items() if k != missing}, format='json').status_code, 400)
        registered = client.post('/api/register', body, format='json')
        self.assertEqual(registered.status_code, 201)
        data = registered.json()
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + data['token'])
        self.assertEqual(client.get('/api/workspace').status_code, 200)
        client.credentials()
        response = client.post('/api/recover', {'email': 'new@test.local', 'recovery_code': data['recovery_code'], 'password': 'Changed-secret-123'}, format='json')
        self.assertEqual(response.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + data['token'])
        self.assertEqual(client.get('/api/workspace').status_code, 401)

    def test_csv_formula_injection(self):
        from .api import csv_safe
        self.assertEqual(csv_safe('=HYPERLINK("x")')[0], "'")
        self.assertEqual(csv_safe('Anna'), 'Anna')

    def test_malformed_identifiers_and_booleans_are_400(self):
        for payload in [{'action': 'submit'}, {'action': 'submit', 'id': 'not-an-id'},
                        {'action': 'create_application', 'offer_id': True},
                        {'action': 'save_draft', 'id': 1, 'bonus_claimed': 'false'}]:
            self.assertEqual(self.client.post('/api/action', payload, format='json').status_code, 400)

    @fixed_totp
    def test_totp_login_and_replay_protection(self):
        import pyotp
        result = self.client.post('/api/action', {'action': 'totp_setup'}, format='json')
        code = pyotp.TOTP(result.json()['secret']).now()
        enabled = self.client.post('/api/action', {'action': 'totp_enable', 'code': code}, format='json')
        self.assertEqual(enabled.status_code, 200)
        anonymous = APIClient()
        payload = {'email': self.candidate.email, 'password': 'Testing-pass-983'}
        self.assertEqual(anonymous.post('/api/login', payload, format='json').status_code, 400)
        payload['code'] = code
        self.assertEqual(anonymous.post('/api/login', payload, format='json').status_code, 200)
        self.assertEqual(anonymous.post('/api/login', payload, format='json').status_code, 400)


class ConcurrencyTests(Fixture, TransactionTestCase):
    def setUp(self):
        self.setup_data()

    def test_two_simultaneous_drafts_create_one_row(self):
        def run():
            close_old_connections()
            try:
                return services.create_application(User.objects.get(pk=self.candidate.pk), self.offers['I'].id).id
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(Application.objects.count(), 1)

    def test_two_simultaneous_publications_publish_once(self):
        self.application()
        self.close_submissions()
        def run():
            close_old_connections()
            try:
                return services.publish(User.objects.get(pk=self.commission.pk), self.offers['I'].id).id
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(Publication.objects.count(), 1)
