"""Regression cases for network state, enrollment and commission improvements."""
from decimal import Decimal
from unittest.mock import patch
import pyotp
from django.db import transaction, DatabaseError
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.test import APIClient
from .tests import Fixture, fixed_totp
from .models import *
from . import services
from .domain import BachelorStrategy
from .demo import avatar_bytes
from .identity import demo_pesel


class RevisionTests(Fixture, TestCase):
    def setUp(self):
        self.setup_data()

    def photo(self, a, version=1):
        return ProfilePhoto.objects.create(user=a.candidate, version=version, file=f'test/photo{version}.png',
                                           original_name='photo.png', sha256=f'{version:064x}')

    def test_bonus_catalog_fee_checkbox_and_photo_approval(self):
        a=self.application(status='submitted')
        a.offer.photo_required=True; a.offer.rule_version='2027.2'; a.offer.save()
        a.bonus_claimed=True; a.save()
        self.photo(a)
        Document.objects.create(application=a,kind='bonus',revision=1,file='test/bonus.pdf',original_name='bonus.pdf',sha256='0'*64)
        data={'decision':'verify','payment_matches':True,'bonus_category':'regional_winner','photo_approved':True}
        services.review(self.commission,a.id,data)
        a.refresh_from_db()
        self.assertEqual(a.bonus_points,30)
        self.assertEqual(a.payment_amount,Decimal(85))
        self.assertTrue(services.current_photo(a.candidate_id).approved_at)
        self.assertEqual(services.calculate(a).score,Decimal(790))
        with self.assertRaises(ValidationError): services.review(self.commission,a.id,dict(data,bonus_points=50))
        with self.assertRaises(DatabaseError),transaction.atomic(): Application.objects.filter(pk=a.id).update(bonus_points=51)
        self.assertEqual(BachelorStrategy().calculate({'M':100,'P1':100,'P2':80,'bonus_points':50}).score,1000)

    def test_profile_document_keeps_version_in_submission_and_photo_is_shared(self):
        original=self.application(); photo=self.photo(original)
        services.approve_photo(self.commission, original.id, True, expected_photo_id=photo.id)
        other=self.application(self.person(1)); self.photo(other)
        a=services.create_application(self.candidate,self.offers['II'].id)
        self.assertFalse(a.documents.exists())
        self.assertFalse(a.payment_approved)
        self.assertEqual(a.status,'draft')
        document = ProfileDocument.objects.create(user=self.candidate, kind='diploma', version=1,
                                                  file='test/diploma.pdf', original_name='diploma.pdf', sha256='a' * 64)
        ProfileDocument.objects.create(user=other.candidate, kind='diploma', version=1,
                                       file='test/other.pdf', original_name='other.pdf', sha256='b' * 64)
        Document.objects.create(application=a, kind='fee', revision=1, file='test/fee.pdf', original_name='fee.pdf', sha256='c' * 64)
        services.submit(self.candidate, a.id)
        ProfileDocument.objects.create(user=self.candidate, kind='diploma', version=2,
                                       file='test/replacement.pdf', original_name='replacement.pdf', sha256='d' * 64)
        self.assertEqual(a.documents.get(kind='education').profile_source_id, document.id)
        self.assertFalse(a.documents.get(kind='fee').profile_source_id)
        workspace = self.client.get('/api/workspace').json()
        self.assertTrue(all(x['photo_approved'] and x['photo']['id'] == photo.id for x in workspace['applications']))
        self.photo(original, 2)
        self.assertFalse(any(x['photo_approved'] for x in self.client.get('/api/workspace').json()['applications']))
        with self.assertRaisesMessage(ValidationError, 'zdjęci'):
            services.approve_photo(self.commission, original.id, True, expected_photo_id=photo.id)

    def test_photo_validation_and_private_access(self):
        a=services.create_application(self.candidate,self.offers['I'].id)
        bad=SimpleUploadedFile('fake.jpg',b'%PDF-fake',content_type='image/jpeg')
        self.assertEqual(self.client.post('/api/profile/photo',{'file':bad},format='multipart').status_code,400)
        good=SimpleUploadedFile('photo.png',avatar_bytes(),content_type='image/png')
        self.assertEqual(self.client.post(f'/api/upload/{a.id}',{'kind':'photo','file':good},format='multipart').status_code,400)
        good=SimpleUploadedFile('photo.png',avatar_bytes(),content_type='image/png')
        uploaded = self.client.post('/api/profile/photo',{'file':good},format='multipart')
        self.assertEqual(uploaded.status_code,200)
        photo=ProfilePhoto.objects.get(user=a.candidate)
        self.assertEqual(uploaded.json()['id'],photo.id)
        self.assertEqual(self.client.get(f'/api/profile/photo/{photo.id}').status_code,200)
        with self.assertRaisesMessage(ValidationError, 'Zgłoszenie zmieniło się'):
            services.approve_photo(self.commission, a.id, True, expected_revision=a.revision + 1)
        self.client.force_authenticate(self.person(1))
        self.assertEqual(self.client.get(f'/api/profile/photo/{photo.id}').status_code,403)

    def test_pesel_is_required_unique_and_write_only(self):
        CandidateIdentity.objects.filter(user=self.candidate).delete()
        a = services.create_application(self.candidate, self.offers['I'].id)
        with self.assertRaisesMessage(ValidationError, 'PESEL'):
            services.submit(self.candidate, a.id)
        body = {'action':'profile','first_name':'Anna','last_name':'Test'}
        self.assertEqual(self.client.post('/api/action',dict(body,pesel='12345678901'),format='json').status_code,400)
        other = self.person(6)
        self.assertEqual(self.client.post('/api/action',dict(body,pesel=demo_pesel(other.pk)),format='json').status_code,400)
        pesel = demo_pesel(self.candidate.pk)
        self.assertEqual(self.client.post('/api/action',dict(body,pesel=pesel),format='json').status_code,200)
        workspace = self.client.get('/api/workspace')
        self.assertTrue(workspace.json()['profile']['has_pesel'])
        self.assertNotIn(pesel.encode(), workspace.content)

    def test_amount_conflicting_with_checked_fee_is_rejected(self):
        a = self.application(status='submitted')
        with self.assertRaisesMessage(ValidationError, 'wpisano inną kwotę'):
            services.review(self.commission, a.id, {'decision':'verify','payment_matches':True,'payment_amount':'50'})
        a.refresh_from_db()
        self.assertEqual(a.status, 'submitted')
        self.assertIsNone(a.payment_amount)

    def test_batch_preview_rolls_back_and_reports_individual_errors(self):
        a=self.application(status='submitted'); self.photo(a)
        b=self.application(self.person(1),status='submitted'); b.bonus_claimed=True; b.save()
        before=AuditEvent.objects.count()
        data={'payment_matches':True,'photo_approved':True,'portfolio_grade':'accepted'}
        preview=services.batch_operation(self.commission,'verify',[a.id,b.id],data,True)
        self.assertEqual(preview['success'],1)
        self.assertIn('Informatyka',preview['results'][0]['subject'])
        a.refresh_from_db(); self.assertEqual(a.status,'submitted'); self.assertEqual(AuditEvent.objects.count(),before)
        result=services.batch_operation(self.commission,'verify',[a.id,b.id],data)
        self.assertEqual(result['success'],1)
        a.refresh_from_db(); self.assertEqual(a.status,'verified')
        with self.assertRaises(PermissionDenied): services.batch_operation(self.commission,'confirm_demo',[a.id],{})

    def test_bulk_portfolio_only_required_where_applicable(self):
        one = self.application(status='submitted')
        required = self.offers['II']
        required.portfolio_required = True
        required.save(update_fields=['portfolio_required'])
        two = self.application(self.person(1), degree='II', score='4.60', status='submitted')
        three = self.application(self.person(2), degree='II', score='4.65', status='submitted')
        Document.objects.create(application=two,kind='portfolio',revision=1,file='test/work.pdf',original_name='work.pdf',sha256='0'*64)
        result = services.batch_operation(self.commission, 'verify', [one.id, two.id, three.id],
                                          {'payment_matches': True, 'portfolio_grade': 'accepted'})
        self.assertEqual(result['success'], 2)
        self.assertIn('Brak portfolio', result['results'][-1]['message'])
        one.refresh_from_db()
        two.refresh_from_db()
        self.assertEqual((one.portfolio_grade, two.portfolio_grade), ('none','accepted'))

    def test_oath_only_after_all_rounds_and_photo_is_frozen(self):
        a=self.application(status='confirmed'); photo=self.photo(a)
        services.approve_photo(self.commission,a.id,True,expected_photo_id=photo.id)
        with self.assertRaises(ValidationError): services.take_oath(self.candidate,a.id,True)
        self.campaign.closed=True; self.campaign.save()
        a.offer.state='launched'; a.offer.save()
        result=services.take_oath(self.candidate,a.id,True)
        self.assertTrue(result.student_number.startswith('PK-DEMO-'))
        self.assertEqual(result.oath_photo_id, photo.id)
        self.assertEqual(services.take_oath(self.candidate,a.id,True).sworn_at,result.sworn_at)
        with self.assertRaises(ValidationError): services.approve_photo(self.commission,a.id,False)
        self.photo(a,2)
        self.assertEqual(self.client.get('/api/workspace').json()['applications'][0]['photo']['id'],photo.id)
        with self.assertRaises(DatabaseError),transaction.atomic():
            ProfilePhoto.objects.filter(pk=photo.id).update(file='changed.png')

    def test_new_edition_retains_history_and_is_idempotent(self):
        a=self.application()
        with self.assertRaises(ValidationError): services.restart_campaign(self.admin,self.campaign.id)
        self.campaign.closed=True; self.campaign.save()
        new=services.restart_campaign(self.admin,self.campaign.id)
        self.assertEqual(new.rounds.count(),7); self.assertEqual(new.offers.count(),3)
        self.assertEqual(services.restart_campaign(self.admin,self.campaign.id).id,new.id)
        self.assertTrue(Application.objects.filter(pk=a.id,offer__campaign=self.campaign).exists())
        self.assertEqual(self.client.get(f'/api/workspace?campaign_id={self.campaign.id}').data['applications'][0]['id'],a.id)
        self.assertFalse(self.client.get('/api/workspace').data['applications'])

    def test_state_changes_and_stale_submit_rejected(self):
        a=services.create_application(self.candidate,self.offers['I'].id)
        before=self.client.get('/api/state').data
        end=Round.objects.get(campaign=self.campaign,degree='I',number=1).application_end
        services.move_clock(self.admin,self.campaign.id,end)
        after=self.client.get('/api/state').data
        self.assertGreater(after['revision'],before['revision'])
        self.assertEqual(next(p for p in after['phases'] if p['degree'] == 'I')['accepting'], False)
        with self.assertRaises(ValidationError): services.submit(self.candidate,a.id)
        reason=self.client.get('/api/catalog').data[0]['block_reason']
        self.assertTrue(reason)

    def test_publication_rejects_a_stale_round_even_when_new_round_accepts_results(self):
        next_round = Round.objects.get(campaign=self.campaign, degree='I', number=2)
        services.move_clock(self.admin, self.campaign.id, next_round.application_end)
        result = services.batch_operation(self.commission, 'publish', [self.offers['I'].id], {
            'expected_rounds': {str(self.offers['I'].id): 1}
        })
        self.assertEqual(result['success'], 0)
        self.assertIn('innej tury', result['results'][0]['message'])
        self.assertFalse(Publication.objects.exists())

    @fixed_totp
    def test_totp_disable_requires_password_code_and_revokes_other_sessions(self):
        from .auth import issue_session
        user=self.candidate; user.totp_secret=pyotp.random_base32(); user.save()
        own,other=issue_session(user),issue_session(user)
        api=APIClient(); api.credentials(HTTP_AUTHORIZATION='Bearer '+own)
        payload={'action':'totp_disable','password':'wrong','code':pyotp.TOTP(user.totp_secret).now()}
        self.assertEqual(api.post('/api/action',payload,format='json').status_code,400)
        payload['password']='Testing-pass-983'
        self.assertEqual(api.post('/api/action',payload,format='json').status_code,200)
        self.assertEqual(Session.objects.filter(user=user).count(),1)
        user.refresh_from_db(); self.assertFalse(user.totp_secret)
        api.credentials(HTTP_AUTHORIZATION='Bearer '+other)
        self.assertEqual(api.get('/api/workspace').status_code,401)
