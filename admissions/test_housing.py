from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from . import housing, offers, profiles, services
from .models import AllowedProfession, Dormitory, HousingApplication, Residence
from .tests import Fixture


class HousingTests(Fixture, TestCase):
    def setUp(self):
        self.setup_data()

    def test_profile_location_suggests_a_postcode_before_saving(self):
        prior = profiles.demo_residence(1)
        Residence.objects.filter(user=self.candidate).update(**prior)
        address = {**{key: prior[key] for key in profiles.ADDRESS_FIELDS}, 'street': 'ul. 3 Maja', 'apartment': '2'}
        data = {'action': 'profile_locate', 'first_name': 'Anna', 'last_name': 'Testowa', 'address': address}
        building = {'city': 'Rzeszów', 'street': '3 Maja', 'number': '1', 'code': '35-030',
                    'x': '22.0018590328604', 'y': '50.0374140925604'}
        similar = {**building, 'street': 'Majowa', 'code': '35-064', 'x': '22.018782'}
        with patch('admissions.profiles.requests.get') as lookup:
            lookup.return_value.json.return_value = {'results': {'1': similar, '2': building}}
            suggestion = self.client.post('/api/action', data, format='json')
            self.assertEqual(suggestion.status_code, 200)
            self.assertEqual(suggestion.json(), {'postal_code_suggestion': '35-030'})
            saved = Residence.objects.get(user=self.candidate)
            for key, value in prior.items():
                self.assertEqual(getattr(saved, key), value)
            self.candidate.refresh_from_db()
            self.assertEqual(self.candidate.last_name, '0')

            address['postal_code'] = '35-030'
            located = self.client.post('/api/action', data, format='json')
            self.assertEqual(located.status_code, 200)
            self.assertEqual(lookup.call_args.kwargs['params']['address'], 'Rzeszów, ul. 3 Maja 1')
        saved.refresh_from_db()
        self.assertEqual((saved.postal_code, saved.street, saved.apartment), ('35-030', 'ul. 3 Maja', '2'))
        self.assertEqual((saved.latitude, saved.longitude), (Decimal('50.037414'), Decimal('22.001859')))
        self.assertEqual(Decimal(str(located.json()['distance'])), profiles.distance_km(saved.latitude, saved.longitude))
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.last_name, 'Testowa')

    def test_ambiguous_location_does_not_offer_a_postcode(self):
        address = Residence(city='Rzeszów', street='3 Maja', building='1', postal_code='35-064')
        first = {'city': 'Rzeszów', 'street': '3 Maja', 'number': '1', 'code': '35-030',
                 'x': '22.001859', 'y': '50.037414'}
        with patch('admissions.profiles.requests.get') as lookup:
            lookup.return_value.json.return_value = {'results': {'1': first, '2': {**first, 'y': '50.05'}}}
            with self.assertRaisesMessage(ValidationError, 'nie wskazał jednoznacznego adresu'):
                profiles.geocode(address)

    def test_pending_application_requires_a_live_degree_application(self):
        for serial, (degree, status) in enumerate([('PG', 'confirmed'), ('I', 'draft'), ('I', 'withdrawn')], 1):
            candidate = self.person(serial)
            self.application(person=candidate, degree=degree, status=status)
            with self.assertRaisesMessage(ValidationError, 'aktywne zgłoszenie'):
                housing.change_request(candidate, self.campaign.id, 'DS1')
        self.application(status='submitted')
        first = housing.change_request(self.candidate, self.campaign.id, 'DS2')
        self.assertEqual(first.pk, housing.change_request(self.candidate, self.campaign.id, 'DS2').pk)
        self.assertEqual(housing.change_request(self.candidate, self.campaign.id, 'DS1').preferred_id, 'DS1')
        self.assertEqual(housing.change_request(self.candidate, self.campaign.id, withdraw=True).status, 'withdrawn')

    def test_distance_selects_residents_and_score_selects_their_dorms(self):
        self.assertEqual(sum(Dormitory.objects.values_list('seats', flat=True)), 1800)
        Dormitory.objects.exclude(code__in=['DS1', 'DS2']).delete()
        Dormitory.objects.update(seats=1)
        bachelor = self.application(score=99, status='confirmed')
        master = self.application(self.person(1), degree='II', score='4.50', status='confirmed')
        nearby = self.application(self.person(2), score=100, status='confirmed')
        excluded = self.application(self.person(3), degree='PG', status='confirmed')
        for app, distance in [(bachelor, 240), (master, 200), (nearby, 10), (excluded, 540)]:
            HousingApplication.objects.create(candidate=app.candidate, campaign=self.campaign, distance_km=distance, preferred_id='DS2')
        self.offers['II'].minimum = 1
        self.offers['II'].save()
        with self.assertRaises(ValidationError):
            services.finalize(self.commission, self.campaign.id)
        self.assertIsNone(housing.housing_workspace(self.commission, self.campaign)['min_distance'])
        self.campaign.demo_clock = self.campaign.end
        self.campaign.save(update_fields=['demo_clock'])
        closed = services.finalize(self.commission, self.campaign.id)
        allocation = {a.candidate_id: a for a in closed.housing_requests.all()}
        self.assertEqual(allocation[bachelor.candidate_id].allocated_id, 'DS1')
        self.assertEqual(allocation[master.candidate_id].allocated_id, 'DS2')
        self.assertEqual(allocation[master.candidate_id].score_index, Decimal('900.00'))
        self.assertEqual(allocation[nearby.candidate_id].status, 'reserve')
        self.assertEqual(allocation[excluded.candidate_id].status, 'ineligible')
        aggregate = housing.housing_workspace(self.commission, closed)
        self.assertEqual(aggregate['min_distance'], Decimal('200.00'))
        self.assertTrue(aggregate['cutoff_used'])
        services.finalize(self.commission, self.campaign.id)
        self.assertEqual(master.candidate.notifications.filter(title='Wynik wniosku o akademik').count(), 1)
        welcome = master.candidate.notifications.get(title='Witaj na Politechnice').message
        self.assertIn('Uruchomiono kierunek Informatyka', welcome)
        self.assertIn('„Moje zgłoszenia”', welcome)
        self.assertIn('„Złóż ślubowanie”', welcome)

    def test_staff_can_edit_and_create_only_before_first_round(self):
        original = self.offers['I']
        AllowedProfession.objects.create(offer=original, name='technik informatyk')
        data = {'campaign_id': self.campaign.id, 'faculty_id': self.faculty.id, 'degree': 'I', 'mode': 'N',
                'name': 'Studia Testowe', 'description': 'Nowa oferta w edycji demonstracyjnej.', 'capacity': '40',
                'fee': '85', 'tuition': '1234.50', 'subjects': ['informatyka'], 'professions': ['technik informatyk']}
        with self.assertRaisesMessage(ValidationError, 'pierwszej tury'):
            offers.create_offer(self.commission, data)
        self.campaign.demo_clock = self.campaign.start - timedelta(days=1)
        self.campaign.save(update_fields=['demo_clock'])
        new = offers.create_offer(self.commission, data)
        self.assertEqual(new.tuition_per_semester, Decimal('1234.50'))
        self.assertEqual(new.allowed_professions.get().name, 'technik informatyk')
        offers.configure_offer(self.commission, {'offer_id': new.id, 'capacity': '45', 'tuition': '1400'})
        new.refresh_from_db()
        self.assertEqual(new.capacity, 45)
        with self.assertRaisesMessage(ValidationError, 'już utworzono'):
            offers.create_offer(self.commission, data)
