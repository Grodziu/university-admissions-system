"""Candidate data, address location and reusable documents."""
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
import re
import unicodedata
from urllib.parse import urlparse

import requests
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db.models import Max
from rest_framework.exceptions import ValidationError

from .identity import normalize_pesel
from .models import CandidateContact, CandidateIdentity, Document, ProfileDocument, Residence

ADDRESS_FIELDS = ('city', 'street', 'building', 'apartment', 'postal_code')
GUGIK_URL = 'https://services.gugik.gov.pl/uug/'
MAIN_CAMPUS = (50.071458, 19.944000)

# Public locations used as fictitious residences during the demonstration.
DEMO_RESIDENCES = (
    ('Tarnów', 'Rynek', '1', '33-100', '50.01250', '20.98820'),
    ('Rzeszów', 'Rynek', '1', '35-064', '50.03710', '22.00490'),
    ('Katowice', 'Rynek', '1', '40-003', '50.26070', '19.02190'),
    ('Nowy Sącz', 'Rynek', '1', '33-300', '49.62500', '20.69100'),
    ('Wrocław', 'Rynek', '1', '50-101', '51.11000', '17.03100'),
    ('Kraków', 'Rynek Główny', '1', '31-042', '50.06161', '19.93669'),
)


def demo_residence(serial):
    city, street, building, postal_code, latitude, longitude = DEMO_RESIDENCES[serial % len(DEMO_RESIDENCES)]
    return {'city': city, 'street': street, 'building': building, 'postal_code': postal_code, 'apartment': '',
            'latitude': Decimal(latitude), 'longitude': Decimal(longitude)}


def address_values(data):
    if not isinstance(data, dict) or any(not isinstance(data.get(key, ''), str) for key in ADDRESS_FIELDS):
        raise ValidationError('Podaj adres zamieszkania.')
    result = {key: ' '.join(data.get(key, '').split()) for key in ADDRESS_FIELDS}
    if not result['city'] or not result['building'] or not re.fullmatch(r'[0-9]{2}-[0-9]{3}', result['postal_code']):
        raise ValidationError('Uzupełnij miejscowość, numer domu i kod pocztowy w formacie 00-000.')
    if any(len(result[key]) > limit for key, limit in [('city',100), ('street',150), ('building',20), ('apartment',20)]):
        raise ValidationError('Dane adresowe są za długie.')
    return result


def phone_value(value):
    phone = re.sub(r'[ ()-]', '', str(value))
    if not re.fullmatch(r'\+?[0-9]{7,15}', phone):
        raise ValidationError('Wpisz poprawny numer telefonu kontaktowego.')
    return phone


def secure_link(value):
    url = str(value).strip()
    try:
        parsed = urlparse(url)
        if url and (len(url) > 500 or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password):
            raise ValueError()
    except ValueError:
        raise ValidationError('Wpisz poprawny link HTTPS do portfolio.') from None
    return url


def notification_address(value):
    if not isinstance(value, str):
        raise ValidationError('Wpisz poprawny adres e-mail do powiadomień.')
    email = value.strip()
    if email:
        try:
            if len(email) > 254:
                raise DjangoValidationError('Address exceeds 254 characters.')
            validate_email(email)
        except DjangoValidationError:
            raise ValidationError('Wpisz poprawny adres e-mail do powiadomień.') from None
    return email


def save_person(user, data, *, new=False):
    # Existing applicants can leave their masked PESEL unchanged when editing a profile.
    if new or data.get('pesel'):
        pesel = normalize_pesel(data.get('pesel',''))
        if CandidateIdentity.objects.exclude(user=user).filter(pesel=pesel).exists():
            raise ValidationError('Ten PESEL jest już przypisany do konta.')
        CandidateIdentity.objects.update_or_create(user=user, defaults={'pesel': pesel})
    elif not CandidateIdentity.objects.filter(user=user).exists():
        raise ValidationError('Podaj PESEL.')
    previous = CandidateContact.objects.filter(user=user).first()
    phone = phone_value(data.get('phone', previous.phone if previous else ''))
    email = notification_address(data.get('notification_email', previous.notification_email if previous else ''))
    CandidateContact.objects.update_or_create(user=user, defaults={
        'phone': phone, 'notification_email': email,
        'portfolio_url': secure_link(data.get('portfolio_url', previous.portfolio_url if previous else ''))})
    old = Residence.objects.filter(user=user).first()
    address = address_values(data['address']) if 'address' in data else None
    if not address and not old:
        raise ValidationError('Podaj adres zamieszkania.')
    if address:
        if not old or any(address[key] != getattr(old,key) for key in ADDRESS_FIELDS if key != 'apartment'):
            address.update(latitude=None, longitude=None)
        Residence.objects.update_or_create(user=user, defaults=address)


def profile_complete(user):
    return (CandidateIdentity.objects.filter(user=user).exists()
            and CandidateContact.objects.filter(user=user).exclude(phone='').exists()
            and Residence.objects.filter(user=user).exists())


def _name(value):
    value = unicodedata.normalize('NFKD', str(value or '').casefold()).replace('ł', 'l')
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


def _street_name(value):
    return re.sub(r'^(?:ulica|ul) ', '', _name(value))


class PostalCodeMismatch(ValidationError):
    def __init__(self, postal_code):
        super().__init__(f'Geoportal wskazuje dla tego adresu kod pocztowy {postal_code}.')
        self.postal_code = postal_code


def _single_location(points):
    return bool(points) and all(distance_km(*point, origin=points[0]) <= Decimal('0.15') for point in points[1:])


def geocode(address):
    query = (f'{address.city}, {address.street} {address.building}' if address.street
             else f'{address.city} {address.building}')
    city, street = _name(address.city), _street_name(address.street)
    building = ''.join(address.building.casefold().split())
    exact, abbreviated = [], []
    try:
        response = requests.get(GUGIK_URL, params={'request': 'GetAddress', 'address': query, 'srid': 4326},
                                timeout=(3, 5), allow_redirects=False)
        response.raise_for_status()
        results = response.json().get('results') or {}
        for point in results.values():
            if (_name(point.get('city')) != city
                    or ''.join(str(point.get('number', '')).casefold().split()) != building):
                continue
            found_street = _street_name(point.get('street'))
            if found_street != street and not (street and found_street.endswith(' ' + street)):
                continue
            latitude, longitude = float(point['y']), float(point['x'])
            if 49 <= latitude <= 55 and 14 <= longitude <= 25:
                group = exact if found_street == street else abbreviated
                group.append(((latitude, longitude), str(point.get('code') or '').strip()))
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
        raise ValidationError('Usługa Geoportalu jest niedostępna. Spróbuj ponownie po odzyskaniu połączenia.') from None

    candidates = exact or abbreviated
    codes = {code for _, code in candidates}
    matches = [coordinates for coordinates, code in candidates
               if code == address.postal_code or codes == {''}]
    if _single_location(matches):
        return tuple(Decimal(str(value)).quantize(Decimal('0.000001')) for value in matches[0])
    if exact and not matches and len(codes) == 1:
        code = next(iter(codes))
        if re.fullmatch(r'[0-9]{2}-[0-9]{3}', code) and _single_location([coordinates for coordinates, _ in exact]):
            raise PostalCodeMismatch(code)
    raise ValidationError('Geoportal nie wskazał jednoznacznego adresu. Sprawdź miejscowość, ulicę, numer domu i kod pocztowy.')


def distance_km(latitude, longitude, origin=MAIN_CAMPUS):
    lat1, lon1 = map(radians, origin)
    lat2, lon2 = map(radians, (float(latitude), float(longitude)))
    value = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    return Decimal(str(2 * 6371.0088 * asin(sqrt(min(1, value))))).quantize(Decimal('0.01'))


def latest_documents(user):
    return ProfileDocument.objects.filter(user=user).order_by('kind','-version').distinct('kind')


def attach_documents(app):
    sources = {item.kind: item for item in latest_documents(app.candidate)}
    kinds = {'education': 'education' if app.offer.degree == 'I' else 'diploma'}
    if app.offer.portfolio_required or app.offer.portfolio_bonus:
        kinds['portfolio'] = 'portfolio'
        contact = CandidateContact.objects.filter(user=app.candidate).first()
        if contact and contact.portfolio_url:
            app.portfolio_url = contact.portfolio_url
    if app.offer.degree == 'I':
        kinds['qualification'] = 'qualification'
        if app.bonus_claimed:
            kinds['bonus'] = 'bonus'
    for kind, source_kind in kinds.items():
        source = sources.get(source_kind)
        if source is None:
            continue
        current = app.documents.filter(kind=kind).order_by('-revision').first()
        if current and current.profile_source_id == source.id:
            continue
        revision = (app.documents.filter(kind=kind).aggregate(maximum=Max('revision'))['maximum'] or 0) + 1
        Document.objects.create(application=app, kind=kind, revision=revision, file=source.file.name,
                                original_name=source.original_name, sha256=source.sha256, profile_source=source)
