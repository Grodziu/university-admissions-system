"""Distance priority for rooms and admission-score priority for preferences."""
from collections import Counter
from decimal import Decimal

from django.db import transaction
from django.db.models import Min
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .campus import HOUSING_FEES, HOUSING_URL
from .domain import RuleError
from .models import Application, Campaign, Dormitory, HousingApplication, Notification, RankingEntry, Residence, User
from .mailing import record_notifications
from .profiles import MAIN_CAMPUS, distance_km
from .services import audit, calculate

ACTIVE_STATUSES = ('submitted', 'correction', 'verified', 'qualified', 'waitlist', 'confirmed')


def housing_block(user, campaign, residence):
    if campaign.closed or campaign.now() >= campaign.end:
        return 'Zakończono składanie wniosków w tej edycji.'
    if campaign.now() < campaign.start:
        return 'Wnioski przyjmujemy od rozpoczęcia naboru.'
    if not Application.objects.filter(candidate=user, offer__campaign=campaign, offer__degree__in=['I','II'],
                                     status__in=ACTIVE_STATUSES).exists():
        return 'Złóż aktywne zgłoszenie na studia I lub II stopnia.'
    if not residence or residence.latitude is None:
        return 'Ustal położenie adresu w zakładce „Mój profil”.'
    return ''


@transaction.atomic
def change_request(user, campaign_id, preferred=None, withdraw=False):
    if user.role != 'candidate':
        raise PermissionDenied('Wniosek o miejsce składa kandydat.')
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    User.objects.select_for_update().get(pk=user.id)
    if campaign.closed or campaign.now() >= campaign.end:
        raise ValidationError('Zakończono składanie wniosków w tej edycji.')
    request = HousingApplication.objects.filter(campaign=campaign, candidate=user).first()
    if withdraw:
        if request and request.status == 'pending':
            request.status = 'withdrawn'
            request.save(update_fields=['status'])
            audit(user, 'housing.withdrawn', request.id, campaign=campaign.id)
        return request
    residence = Residence.objects.filter(user=user).first()
    reason = housing_block(user, campaign, residence)
    if reason:
        raise ValidationError(reason)
    if not isinstance(preferred, str) or not Dormitory.objects.filter(code=preferred).exists():
        raise ValidationError('Wybierz preferowany dom studencki.')
    distance = distance_km(residence.latitude, residence.longitude)
    if request and request.status == 'pending' and request.preferred_id == preferred and request.distance_km == distance:
        return request
    request, _ = HousingApplication.objects.update_or_create(
        candidate=user, campaign=campaign, defaults={'preferred_id': preferred, 'status': 'pending',
                                                     'distance_km': distance, 'submitted_at': timezone.now()})
    audit(user, 'housing.submitted', request.id, campaign=campaign.id, preferred=preferred)
    return request


def dorm_data(dorm):
    return {'code': dorm.code, 'name': dorm.name, 'address': dorm.address, 'description': dorm.description, 'seats': dorm.seats,
            'latitude': float(dorm.latitude), 'longitude': float(dorm.longitude)}


def housing_workspace(user, campaign, residence=None):
    dorms = list(Dormitory.objects.all())
    query = campaign.housing_requests
    result = {'dorms': [dorm_data(d) for d in dorms], 'capacity': sum(d.seats for d in dorms),
              'ends_at': campaign.end, 'published': campaign.closed, 'campus': MAIN_CAMPUS}
    if user.role == 'candidate':
        entry = query.filter(candidate=user).select_related('allocated').first()
        result.update(
            block=housing_block(user,campaign,residence),
            my_distance=distance_km(residence.latitude,residence.longitude) if residence and residence.latitude is not None else None,
            request={'preferred': entry.preferred_id, 'distance': entry.distance_km, 'status': entry.status,
                     'label': entry.get_status_display(), 'allocated': dorm_data(entry.allocated) if entry.allocated else None,
                     'score': entry.score_index if campaign.closed else None} if entry else None)
    else:
        totals = Counter(query.values_list('status',flat=True))
        awarded = query.filter(status='awarded')
        result.update(counts=dict(totals), per_dorm=dict(Counter(awarded.values_list('allocated_id',flat=True))),
                      min_distance=awarded.aggregate(distance=Min('distance_km'))['distance'] if campaign.closed else None,
                      cutoff_used=campaign.closed and totals['reserve'] > 0)
    return result


def admission_index(app, score):
    if score is None:
        try:
            score = calculate(app).score
        except RuleError:
            return Decimal('0')
    return score * 200 if app.offer.degree == 'II' else score


def allocate_dorms(campaign, actor):
    """Called during campaign finalization with the campaign row locked."""
    pending = list(campaign.housing_requests.filter(status='pending'))
    if not pending:
        return
    enrollments = list(Application.objects.filter(
        offer__campaign=campaign, offer__state='launched', offer__degree__in=['I','II'], status='confirmed',
        candidate_id__in=[row.candidate_id for row in pending]).select_related('offer'))
    ranking = dict(RankingEntry.objects.filter(application_id__in=[app.id for app in enrollments])
                   .order_by('application_id','-publication__published_at','-pk').distinct('application_id')
                   .values_list('application_id','score'))
    best = {}
    for app in sorted(enrollments,key=lambda row:row.pk):
        score = admission_index(app, ranking.get(app.id))
        if app.candidate_id not in best or score > best[app.candidate_id][1]:
            best[app.candidate_id] = app, score
    eligible = []
    for row in pending:
        if row.candidate_id in best:
            row.enrollment, row.score_index = best[row.candidate_id]
            eligible.append(row)
            row.status = 'reserve'
        else:
            row.status = 'ineligible'
    remaining = {d.code:d.seats for d in Dormitory.objects.all()}
    eligible.sort(key=lambda row: (-row.distance_km, -row.score_index, row.submitted_at, row.pk))
    winners = eligible[:sum(remaining.values())]
    for row in sorted(winners,key=lambda row:(-row.score_index, -row.distance_km, row.submitted_at, row.pk)):
        code = row.preferred_id if remaining[row.preferred_id] else next(key for key, seats in remaining.items() if seats)
        remaining[code] -= 1
        row.allocated_id = code
        row.status = 'awarded'
    HousingApplication.objects.bulk_update(pending,['enrollment','score_index','status','allocated'],batch_size=250)
    names = dict(Dormitory.objects.values_list('code','name'))
    messages = []
    for row in pending:
        if row.status == 'awarded':
            text = (f'Gratulacje! Przyznano miejsce w {row.allocated_id} „{names[row.allocated_id]}”. '
                    f'Termin zakwaterowania i dane do wpłaty sprawdzisz u administracji osiedla. {HOUSING_URL} Cennik: {HOUSING_FEES}')
        elif row.status == 'reserve':
            text = 'Twój wniosek jest na liście rezerwowej. Sprawdź dalsze ogłoszenia administracji osiedla.'
        else:
            text = 'Przydział wymaga potwierdzonego miejsca na uruchomionych studiach I lub II stopnia.'
        messages.append(Notification(user_id=row.candidate_id,title='Wynik wniosku o akademik',message=text))
    record_notifications(messages)
    audit(actor,'housing.published',campaign.id,awarded=len(winners),requests=len(pending))
