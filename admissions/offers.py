"""Editing the catalogue before the first round of an edition."""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .domain import number
from .models import AllowedProfession, AllowedSubject, Campaign, Faculty, Offer, Program
from .services import audit, locked_offer, require_staff


def planning_open(campaign, degree):
    return not campaign.closed and any(round_.number == 1 and round_.degree == degree and campaign.now() < round_.start
                                       for round_ in campaign.rounds.all())


def _choices(data, key, existing, legal):
    values = data.get(key, existing)
    if not isinstance(values,list) or len(values) > 100 or any(not isinstance(x,str) or x not in legal for x in values):
        raise ValidationError('Wybierz pozycje z katalogu rozszerzeń i kwalifikacji.')
    return sorted(set(values))


def save_terms(offer, data):
    minimum = number(data.get('minimum',offer.minimum),1,2000)
    capacity = number(data.get('capacity',offer.capacity),minimum,2000)
    if minimum != int(minimum) or capacity != int(capacity):
        raise ValidationError('Minimum uruchomienia i limit miejsc muszą być liczbami całkowitymi.')
    offer.minimum, offer.capacity = int(minimum), int(capacity)
    offer.fee = number(data.get('fee',offer.fee),1,10000)
    paid = offer.mode == 'N' or offer.degree == 'PG'
    offer.tuition_per_semester = number(data.get('tuition',offer.tuition_per_semester),1,100000) if paid else None
    offer.portfolio_required = data.get('portfolio_required',offer.portfolio_required)
    offer.portfolio_bonus = offer.degree == 'I' and data.get('portfolio_bonus',offer.portfolio_bonus)
    subjects = professions = []
    if offer.degree == 'I':
        current_subjects = list(offer.allowed_subjects.values_list('subject',flat=True)) if offer.pk else []
        current_professions = list(offer.allowed_professions.values_list('name',flat=True)) if offer.pk else []
        subjects = _choices(data,'subjects',current_subjects,set(AllowedSubject.objects.values_list('subject',flat=True)))
        professions = _choices(data,'professions',current_professions,set(AllowedProfession.objects.values_list('name',flat=True)))
        if not (subjects or professions):
            raise ValidationError('Wybierz co najmniej jedno rozszerzenie lub kwalifikację technika.')
    offer.save()
    offer.allowed_subjects.exclude(subject__in=subjects).delete()
    offer.allowed_professions.exclude(name__in=professions).delete()
    AllowedSubject.objects.bulk_create([AllowedSubject(offer=offer,subject=x) for x in subjects],ignore_conflicts=True)
    AllowedProfession.objects.bulk_create([AllowedProfession(offer=offer,name=x) for x in professions],ignore_conflicts=True)
    return offer


@transaction.atomic
def configure_offer(user, data):
    require_staff(user)
    offer = locked_offer(data['offer_id'])
    if not planning_open(offer.campaign,offer.degree) or offer.applications.exists():
        raise ValidationError('Parametry oferty zapiszesz przed rozpoczęciem pierwszej tury i złożeniem pierwszego zgłoszenia.')
    save_terms(offer,data)
    audit(user,'offer.configured',offer.id,capacity=offer.capacity,fee=str(offer.fee))
    return offer


@transaction.atomic
def create_offer(user, data):
    require_staff(user)
    campaign = Campaign.objects.select_for_update().get(pk=data['campaign_id'])
    faculty = Faculty.objects.get(pk=data['faculty_id'])
    degree, mode = data.get('degree'), data.get('mode')
    if degree not in ['I','II','PG'] or mode not in ['S','N'] or degree == 'PG' and mode != 'N':
        raise ValidationError('Wybierz stopień i tryb właściwe dla oferty.')
    if not planning_open(campaign,degree):
        raise ValidationError('Ofertę można dodać przed rozpoczęciem pierwszej tury danego stopnia.')
    name = ' '.join(str(data.get('name','')).split())
    description = str(data.get('description','')).strip()
    if not name or len(name) > 200 or len(description) > 3000:
        raise ValidationError('Podaj nazwę kierunku i opis do 3000 znaków.')
    program = Program.objects.filter(faculty=faculty,name__iexact=name).first()
    if not program:
        if not description:
            raise ValidationError('Dodaj krótki opis nowego kierunku.')
        program = Program.objects.create(faculty=faculty,name=name,description=description,illustrative=True)
    if Offer.objects.filter(campaign=campaign,program=program,degree=degree,mode=mode).exists():
        raise ValidationError('Taką ofertę już utworzono w tej edycji.')
    default_minimum = 20 if degree == 'I' else 10
    offer = Offer(campaign=campaign,program=program,degree=degree,mode=mode,capacity=30,minimum=default_minimum,
                  photo_required=True,rule_version='2027.2')
    save_terms(offer,data)
    audit(user,'offer.created',offer.id,campaign=campaign.id,degree=degree,mode=mode)
    return offer
