import csv
import hashlib
import io
from pathlib import Path
import secrets
import time
from collections import Counter, defaultdict
import pyotp
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError, ObjectDoesNotExist
from django.core.validators import validate_email
from django.db import transaction, IntegrityError
from django.db.models import Q, Max, Count, Prefetch
from django.http import FileResponse, HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import exception_handler as drf_handler
from . import housing, offers as catalogue, profiles, services
from .auth import issue_session
from .domain import RuleError, number
from .identity import demo_pesel
from .models import *
from .policies import BONUS_CATALOG, STATUS_HELP, OATH_TEXT
from .version import VERSION


class LoginThrottle(AnonRateThrottle):
    scope = 'login'


def exception_handler(exc, context):
    if isinstance(exc, (RuleError, DjangoValidationError)):
        exc = ValidationError(str(exc))
    elif isinstance(exc, ObjectDoesNotExist):
        from rest_framework.exceptions import NotFound
        exc = NotFound('Nie znaleziono wskazanego rekordu.')
    elif isinstance(exc, IntegrityError):
        exc = ValidationError('Operacja narusza spójność danych lub rekord już istnieje. Odśwież widok.')
    return drf_handler(exc, context)


def user_data(user):
    return {'id': user.id, 'email': user.email, 'first_name': user.first_name,
            'last_name': user.last_name, 'role': user.role, 'role_label': user.get_role_display(),
            'totp_enabled': bool(user.totp_secret)}


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    campaign = services.current_campaign()
    return Response({'ready': campaign is not None, 'version': VERSION,
                     'demo': bool(campaign and campaign.demo_clock is not None)})


def requested_campaign(request):
    value = request.query_params.get('campaign_id')
    if value:
        if not value.isdigit():
            raise ValidationError('Niepoprawna edycja rekrutacji.')
        return Campaign.objects.get(pk=int(value))
    return services.current_campaign()


def check_totp(user, code):
    if not user.totp_secret:
        return
    totp = pyotp.TOTP(user.totp_secret)
    current_step = int(time.time()) // 30
    if current_step <= user.totp_last_step or not totp.verify(str(code), valid_window=0):
        raise ValidationError('Podaj aktualny, nieużyty kod z aplikacji uwierzytelniającej.')
    user.totp_last_step = current_step
    user.save(update_fields=['totp_last_step'])


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
@transaction.atomic
def login(request):
    email = str(request.data.get('email', '')).strip().lower()
    user = authenticate(username=email, password=request.data.get('password', ''))
    if not user:
        raise ValidationError('Niepoprawny adres e-mail lub hasło.')
    user = User.objects.select_for_update().get(pk=user.pk)
    check_totp(user, request.data.get('code', ''))
    return Response({'token': issue_session(user), 'user': user_data(user)})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
@transaction.atomic
def register(request):
    email = str(request.data.get('email', '')).strip().lower()
    validate_email(email)
    if len(email) > 150:
        raise ValidationError('Adres e-mail może mieć najwyżej 150 znaków.')
    password = str(request.data.get('password', ''))
    first, last = str(request.data.get('first_name', '')).strip(), str(request.data.get('last_name', '')).strip()
    if not first or not last or len(first) > 100 or len(last) > 100:
        raise ValidationError('Wpisz imię i nazwisko, każde do 100 znaków.')
    user = User(username=email, email=email, first_name=first, last_name=last)
    validate_password(password, user)
    recovery = secrets.token_hex(16)
    user.recovery_hash = make_password(recovery)
    user.set_password(password)
    user.save()
    profiles.save_person(user,request.data,new=True)
    services.audit(user, 'account.created', user.id)
    return Response({'token': issue_session(user), 'user': user_data(user), 'recovery_code': recovery}, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
@transaction.atomic
def recover(request):
    user = User.objects.select_for_update().filter(email=str(request.data.get('email', '')).lower().strip()).first()
    # Always perform a password hash comparison, including for an unknown account.
    hashed = user.recovery_hash if user and user.recovery_hash else make_password(secrets.token_hex(16))
    if not check_password(str(request.data.get('recovery_code', '')), hashed) or not user:
        raise ValidationError('Adres e-mail lub kod odzyskiwania jest niepoprawny.')
    password = str(request.data.get('password', ''))
    validate_password(password, user)
    recovery = secrets.token_hex(16)
    user.set_password(password)
    user.recovery_hash = make_password(recovery)
    user.totp_secret = user.totp_pending = ''
    user.totp_last_step = 0
    user.save()
    Session.objects.filter(user=user).delete()
    services.audit(user, 'account.recovered', user.id)
    return Response({'recovery_code': recovery})


def offer_data(offer, application_counts, published):
    current = services.active_round(offer)
    stats = getattr(offer, 'stats', None)
    confirmed = stats.confirmed if stats else 0
    counts = application_counts.get((offer.id, current.id), {}) if current else {}
    in_progress = sum(counts.get(state, 0) for state in ('submitted', 'correction', 'verified', 'qualified'))
    interested = confirmed + in_progress
    threatened = bool(offer.degree in ['I', 'II'] and current and current.number >= 2 and
                      offer.state == 'open' and interested < offer.minimum)
    current_publication = (offer.id, current.id) in published if current else False
    phase, publication_message = services.publication_status(offer, current, counts, current_publication)
    return {'id': offer.id, 'program_id': offer.program_id, 'name': offer.program.name, 'faculty': offer.program.faculty.code,
            'faculty_name': offer.program.faculty.name, 'color': offer.program.faculty.color,
            'partners': [f.code for f in offer.program.partner_faculties.all()],
            'degree': offer.degree, 'degree_label': offer.get_degree_display(), 'mode': offer.mode,
            'mode_label': offer.get_mode_display(), 'description': offer.program.description,
            'capacity': offer.capacity, 'minimum': offer.minimum, 'confirmed': confirmed,
            'launch_ready': offer.state == 'launched' or offer.state == 'open' and confirmed >= offer.minimum,
            'configurable': catalogue.planning_open(offer.campaign, offer.degree) and not (stats and stats.applications),
            'awaiting_confirmation': counts.get('qualified', 0),
            'pending_review': counts.get('submitted', 0) + counts.get('correction', 0),
            'interested': interested, 'fee': str(offer.fee), 'state': offer.state,
            'tuition_per_semester': str(offer.tuition_per_semester) if offer.tuition_per_semester is not None else None,
            'publication_phase': phase, 'publication_message': publication_message,
            'state_label': offer.get_state_display(), 'threatened': threatened,
            'portfolio_required': offer.portfolio_required, 'portfolio_bonus': offer.portfolio_bonus,
            'photo_required': offer.photo_required, 'campaign_id': offer.campaign_id,
            'campaign_closed': offer.campaign.closed, 'block_reason': services.submission_block_reason(offer),
            'round': current.number if current else None,
            'application_end': current.application_end.isoformat() if current else None,
            'round_end': current.end.isoformat() if current else None,
            'open': bool(current and offer.campaign.now() < current.application_end and offer.state == 'open' and not offer.campaign.closed),
            'subjects': [s.subject for s in offer.allowed_subjects.all()],
            'professions': [p.name for p in offer.allowed_professions.all()],
            'source': offer.program.source, 'illustrative': offer.program.illustrative}


@api_view(['GET'])
@permission_classes([AllowAny])
def lecturers(request):
    from .academic_staff import catalog
    return Response(catalog())


def photo_data(photo):
    if not photo:
        return None
    return {'id': photo.id, 'name': photo.original_name, 'version': photo.version, 'approved': bool(photo.approved_at),
            'url': f'/profile/photo/{photo.id}'}


def application_data(app, profile_photo, has_pesel):
    entry = next(iter(app.latest_rankings), None)
    photo = app.oath_photo if app.sworn_at else profile_photo
    oath_block = services.oath_problem(app, photo, has_pesel) if not app.sworn_at else ''
    card_from, card_until = services.student_card_period(app.offer.campaign) if app.sworn_at else (None, None)
    result = None
    if app.input_snapshot:
        try:
            result = services.calculate(app).explanation
        except RuleError:
            pass
    help_text = STATUS_HELP.get(app.status, '')
    if app.status == 'confirmed':
        stats = getattr(app.offer, 'stats', None)
        count = stats.confirmed if stats else 0
        if app.offer.state == 'launched':
            help_text = 'Kierunek został uruchomiony. Masz potwierdzone miejsce.'
        elif count >= app.offer.minimum:
            help_text = 'Potwierdzono wymagane minimum miejsc. Kierunek ma wystartować.'
        else:
            help_text = f'Masz potwierdzone miejsce. Do uruchomienia kierunku potrzeba jeszcze {app.offer.minimum - count} potwierdzeń.'
    return {'id': app.id, 'public_id': str(app.public_id), 'offer_id': app.offer_id,
            'name': app.offer.program.name, 'degree': app.offer.degree, 'mode': app.offer.get_mode_display(),
            'color': app.offer.program.faculty.color, 'faculty': app.offer.program.faculty.code,
            'round': app.round.number, 'status': app.status, 'status_label': app.get_status_display(),
            'feedback': app.feedback, 'revision': app.revision, 'portfolio_url': app.portfolio_url,
            'bonus_claimed': app.bonus_claimed, 'payment_approved': app.payment_approved,
            'bonus_points': app.bonus_points, 'bonus_category': app.bonus_category,
            'photo': photo_data(photo), 'photo_approved': bool(photo and photo.approved_at), 'photo_required': app.offer.photo_required,
            'mode_code': app.offer.mode, 'is_demo': app.candidate.is_demo,
            'status_help': help_text,
            'campaign_closed': app.offer.campaign.closed, 'offer_state': app.offer.state,
            'sworn_at': app.sworn_at, 'student_number': app.student_number,
            'card_valid_from': card_from, 'card_valid_until': card_until,
            'can_oath': not app.sworn_at and not oath_block, 'oath_block': oath_block,
            'fee': str(app.offer.fee), 'portfolio_grade': app.portfolio_grade,
            'submitted_at': app.submitted_at, 'input': app.input_snapshot,
            'candidate': f"{app.input_snapshot.get('first_name', app.candidate.first_name)} {app.input_snapshot.get('last_name', app.candidate.last_name)}",
            'email': app.candidate.email, 'preview': result,
            'documents': [{'id': d.id, 'kind': d.kind, 'label': d.get_kind_display(), 'name': d.original_name, 'revision': d.revision,
                           'from_profile': bool(d.profile_source_id), 'profile_source_id': d.profile_source_id}
                          for d in app.documents.all() if d.kind != 'photo'],
            'result': {'rank': entry.rank, 'score': str(entry.score) if entry.score is not None else None,
                       'explanation': entry.explanation, 'version': entry.publication.version,
                       'round': entry.publication.round.number, 'decision': entry.decision} if entry else None}


@api_view(['GET'])
@permission_classes([AllowAny])
def catalog(request):
    campaign = requested_campaign(request)
    counts = defaultdict(dict)
    for row in (Application.objects.filter(offer__campaign=campaign)
                .values('offer_id', 'round_id', 'status').annotate(total=Count('id'))):
        counts[(row['offer_id'], row['round_id'])][row['status']] = row['total']
    published = set(Publication.objects.filter(offer__campaign=campaign).values_list('offer_id', 'round_id'))
    offers = (Offer.objects.filter(campaign=campaign).select_related('program__faculty', 'campaign', 'stats')
              .prefetch_related('program__partner_faculties', 'allowed_subjects', 'allowed_professions', 'campaign__rounds')
              .order_by('program__faculty_id', 'program__name', 'degree', 'mode'))
    return Response([offer_data(offer, counts, published) for offer in offers])


@api_view(['GET'])
@permission_classes([AllowAny])
def thresholds(request):
    campaign = requested_campaign(request)
    rounds = list(campaign.rounds.all())
    latest = Publication.objects.filter(offer__campaign=campaign).order_by('offer_id', 'round_id', '-version').distinct('offer_id', 'round_id')
    by_offer_round = {(pub.offer_id, pub.round_id): pub for pub in latest}
    rows = []
    for offer in Offer.objects.filter(campaign=campaign).select_related('program__faculty').order_by('degree', 'mode', 'program__name'):
        values = []
        for round_ in rounds:
            if round_.degree != offer.degree:
                continue
            pub = by_offer_round.get((offer.id, round_.id))
            if offer.state == 'canceled':
                label = 'nie uruchomiono'
            elif not pub:
                label = '-'
            elif offer.degree == 'PG':
                label = f'kolejność zgłoszeń • {pub.qualified_count} zakwal.'
            elif pub.cutoff is None:
                label = 'brak zakwalifikowanych'
            else:
                label = f'{pub.cutoff:.2f}' + (' pkt' if offer.degree == 'I' else ' (średnia)')
            values.append({'round': round_.number, 'label': label, 'version': pub.version if pub else None,
                           'historical_cutoff': str(pub.cutoff) if pub and pub.cutoff is not None else None})
        rows.append({'offer_id': offer.id, 'name': offer.program.name, 'faculty': offer.program.faculty.code,
                     'degree': offer.degree, 'mode': offer.mode, 'state': offer.state, 'values': values})
    return Response(rows)


def workspace_revision():
    # Audit is append-only. Counting committed events also detects commits arriving out of sequence.
    return AuditEvent.objects.exclude(action__in=['document.downloaded', 'backup.created']).count()


def campaign_phases(rounds, now):
    return [{'degree': r['degree'], 'number': r['number'], 'accepting': now < r['application_end']}
            for r in rounds if r['start'] <= now < r['end']]


@api_view(['GET'])
def workspace(request):
    revision = workspace_revision()
    user = request.user
    campaign = requested_campaign(request)
    now = campaign.now()
    rounds = list(campaign.rounds.values('degree', 'number', 'start', 'application_end', 'end'))
    latest_rankings = (RankingEntry.objects.select_related('publication__round')
                       .order_by('application_id', '-publication__published_at', '-id').distinct('application_id'))
    apps = (Application.objects.filter(offer__campaign=campaign)
            .select_related('candidate', 'offer__program__faculty', 'offer__campaign', 'offer__stats', 'round', 'oath_photo')
            .prefetch_related(Prefetch('documents', Document.objects.order_by('kind', '-revision')),
                              Prefetch('ranking_entries', latest_rankings, to_attr='latest_rankings')))
    if user.role == 'candidate':
        apps = apps.filter(candidate=user)
    apps = list(apps.order_by('-created_at', '-id'))
    photo_users = {app.candidate_id for app in apps} | {user.id}
    photos = {p.user_id: p for p in (ProfilePhoto.objects.filter(user_id__in=photo_users)
                                   .order_by('user_id', '-version').distinct('user_id'))}
    identity_users = set(CandidateIdentity.objects.filter(user_id__in=photo_users).values_list('user_id', flat=True))
    average, diploma = AcademicAverage.objects.filter(user=user).first(), Diploma.objects.filter(user=user).first()
    contact = CandidateContact.objects.filter(user=user).first()
    residence = Residence.objects.filter(user=user).first() if user.role == 'candidate' else None
    data = {'revision': revision, 'user': user_data(user), 'campaign': {
        'id': campaign.id, 'name': campaign.name, 'now': now, 'start': campaign.start,
        'end': campaign.end, 'demo': campaign.demo_clock is not None, 'closed': campaign.closed, 'scenario': campaign.demo_scenario,
        'rounds': rounds, 'phases': campaign_phases(rounds, now)},
        'applications': [application_data(app, photos.get(app.candidate_id), app.candidate_id in identity_users) for app in apps],
        'profile': {'phone': contact.phone if contact else '', 'average': str(average.value) if average else '',
                    'has_pesel': user.id in identity_users, 'photo': photo_data(photos.get(user.id)),
                    'complete': bool(user.id in identity_users and residence and contact and contact.phone),
                    'address': {key:getattr(residence,key) if residence else '' for key in profiles.ADDRESS_FIELDS},
                    'located': bool(residence and residence.latitude is not None),
                    'portfolio_url': contact.portfolio_url if contact else '',
                    'notification_email': contact.notification_email if contact else '',
                    'mail_enabled': settings.PK_MAIL_ENABLED,
                    'documents': [profile_document_data(doc) for doc in profiles.latest_documents(user)] if user.role == 'candidate' else [],
                    'document_kinds': list(ProfileDocument.Kind.choices),
                    'diploma': diploma.title if diploma else '', 'exams': list(user.exam_results.values('subject', 'level', 'value'))},
        'housing': housing.housing_workspace(user, campaign, residence),
        'notifications': list(user.notifications.order_by('-created_at').values()[:100]),
        'unread_notifications': user.notifications.filter(read=False).count(),
        'professions': sorted(set(AllowedProfession.objects.values_list('name', flat=True))),
        'subjects': sorted(set(AllowedSubject.objects.values_list('subject', flat=True))),
        'bonus_catalog': BONUS_CATALOG, 'oath_text': OATH_TEXT,
        'campaigns': list(Campaign.objects.order_by('-start', '-id').values('id', 'name', 'closed'))}
    if user.role in ['commission', 'admin']:
        data['faculties'] = list(Faculty.objects.order_by('name').values('id','code','name','color'))
        data['can_create_offer'] = any(not campaign.closed and r['number']==1 and now < r['start'] for r in rounds)
        submitted = [app for app in apps if app.submitted_at is not None]
        totals = Counter(app.status for app in submitted)
        data['insights'] = {
            'candidates': len({app.candidate_id for app in submitted}),
            'applications': len(submitted),
            'pending': totals['submitted'] + totals['correction'],
            'qualified': totals['qualified'],
            'confirmed': totals['confirmed'],
            'by_offer': dict(Counter(app.offer_id for app in submitted)),
            'by_round': [{'degree': degree, 'round': round_number, 'applications': count}
                         for (degree, round_number), count in sorted(Counter(
                             (app.offer.degree, app.round.number) for app in submitted).items())],
        }
    if user.role == 'admin':
        data['users'] = [user_data(u) for u in User.objects.filter(is_active=True).exclude(email__startswith='synthetic')[:100]]
        data['audit'] = list(AuditEvent.objects.order_by('-created_at').values('created_at', 'action', 'entity', 'details', 'actor__email')[:150])
    return Response(data)


@api_view(['GET'])
def state(request):
    revision = workspace_revision()
    campaign = requested_campaign(request)
    now = campaign.now()
    rounds = campaign.rounds.values('degree', 'number', 'start', 'application_end', 'end')
    return Response({'revision': revision,
                     'campaign_id': campaign.id, 'closed': campaign.closed, 'now': now,
                     'server_time': timezone.now(), 'phases': campaign_phases(rounds, now),
                     'latest_campaign_id': services.current_campaign().id})


@api_view(['POST'])
@transaction.atomic
def action(request):
    user, data = request.user, request.data
    if not isinstance(data, dict):
        raise ValidationError('Żądanie musi zawierać obiekt JSON.')
    name = data.get('action')
    identifiers = {
        'create_application': ['offer_id'], 'configure_offer': ['offer_id'], 'publish': ['offer_id'],
        'create_offer': ['campaign_id','faculty_id'], 'housing_apply': ['campaign_id'], 'housing_withdraw': ['campaign_id'],
        'save_draft': ['id'], 'submit': ['id'], 'review': ['id'], 'confirm': ['id'],
        'withdraw': ['id'], 'continue': ['id'], 'clock': ['campaign_id'], 'finalize': ['campaign_id'], 'role': ['user_id'],
        'photo_review': ['id'], 'oath': ['id'], 'restart': ['campaign_id'], 'demo_scenario': ['campaign_id']}
    for field_name in identifiers.get(name, []):
        value = data.get(field_name)
        if type(value) is not int or not 0 < value < 2**63:
            raise ValidationError('Brak poprawnego identyfikatora: ' + field_name)
    for field_name in ['expected_round', 'expected_revision']:
        if field_name in data and (type(data[field_name]) is not int or not 0 < data[field_name] < 2**63):
            raise ValidationError('Niepoprawna wersja danych. Odśwież widok.')
    photo_id = data.get('expected_photo_id')
    if photo_id is not None and (type(photo_id) is not int or not 0 < photo_id < 2**63):
        raise ValidationError('Niepoprawna wersja zdjęcia. Odśwież widok.')
    if name in ['photo_review', 'review'] and data.get('photo_approved') is True and photo_id is None:
        raise ValidationError('Wskaż obejrzaną wersję zdjęcia. Odśwież widok zgłoszenia.')
    if name == 'batch' and data.get('operation') == 'verify' and data.get('photo_approved') is True and 'expected_photos' not in data:
        raise ValidationError('Wskaż obejrzane wersje zdjęć. Odśwież listę zgłoszeń.')
    if 'expected_photos' in data:
        photos = data['expected_photos']
        if not isinstance(photos, dict) or len(photos) > 250 or any(v is not None and (type(v) is not int or not 0 < v < 2**63) for v in photos.values()):
            raise ValidationError('Niepoprawne wersje zdjęć. Odśwież widok.')
    for field_name in ['expected_rounds', 'expected_revisions']:
        if field_name in data:
            versions = data[field_name]
            if not isinstance(versions, dict) or len(versions) > 250 or any(type(v) is not int or not 0 < v < 2**63 for v in versions.values()):
                raise ValidationError('Niepoprawne wersje danych. Odśwież widok.')
    for field_name in ['bonus_claimed', 'bonus_approved', 'portfolio_required', 'portfolio_bonus', 'payment_matches', 'photo_approved', 'accepted', 'preview']:
        if field_name in data and type(data[field_name]) is not bool:
            raise ValidationError('Niepoprawna wartość logiczna: ' + field_name)
    if data.get('correction') is not None:
        correction = data['correction']
        if not isinstance(correction, dict) or type(correction.get('application_id')) is not int:
            raise ValidationError('Korekta musi wskazywać zgłoszenie.')
    if name == 'logout':
        request.auth.delete()
    elif name in ('profile', 'profile_locate'):
        if user.role != 'candidate':
            raise PermissionDenied('Dane rekrutacyjne są dostępne na koncie kandydata.')
        coordinates = None
        if name == 'profile_locate':
            address = Residence(**profiles.address_values(data.get('address')))
            try:
                coordinates = profiles.geocode(address)
            except profiles.PostalCodeMismatch as error:
                return Response({'postal_code_suggestion': error.postal_code})
        User.objects.select_for_update().get(pk=user.pk)
        profiles.save_person(user,data)
        first, last = str(data.get('first_name', '')).strip(), str(data.get('last_name', '')).strip()
        if not first or not last or max(len(first), len(last)) > 100:
            raise ValidationError('Uzupełnij imię i nazwisko (do 100 znaków).')
        user.first_name, user.last_name = first, last
        user.save(update_fields=['first_name', 'last_name'])
        diploma = str(data.get('diploma', '')).strip()
        if len(diploma) > 120:
            raise ValidationError('Tytuł może mieć do 120 znaków.')
        if diploma:
            Diploma.objects.update_or_create(user=user, defaults={'title': diploma})
        else:
            Diploma.objects.filter(user=user).delete()
        average = data.get('average')
        if average not in [None, '']:
            AcademicAverage.objects.update_or_create(user=user, defaults={'value': number(average, 2, 5)})
        else:
            AcademicAverage.objects.filter(user=user).delete()
        exams = data.get('exams', [])
        if not isinstance(exams, list) or len(exams) > 15:
            raise ValidationError('Dodaj maksymalnie 15 wyników.')
        allowed_subjects = set(AllowedSubject.objects.values_list('subject', flat=True)) | {'matematyka'}
        allowed_professions = set(AllowedProfession.objects.values_list('name', flat=True))
        user.exam_results.all().delete()
        for exam in exams:
            if not isinstance(exam, dict):
                raise ValidationError('Wynik egzaminu musi zawierać przedmiot, poziom i wartość.')
            level, subject = exam.get('level'), exam.get('subject')
            if level not in ['basic', 'extended', 'technical'] or subject not in (allowed_professions if level == 'technical' else allowed_subjects):
                raise ValidationError('Niepoprawny przedmiot lub kwalifikacja.')
            if level == 'basic' and subject != 'matematyka':
                raise ValidationError('Wskaźnik uwzględnia poziom podstawowy tylko z matematyki.')
            ExamResult.objects.create(user=user, level=level, subject=subject, value=number(exam.get('value')))
        services.audit(user, 'profile.updated', user.id)
        if coordinates is not None:
            latitude, longitude = coordinates
            Residence.objects.filter(user=user).update(latitude=latitude, longitude=longitude)
            services.audit(user, 'profile.residence_located', user.id)
            return Response({'distance': profiles.distance_km(latitude, longitude)})
    elif name == 'profile_demo_identity':
        campaign = services.current_campaign()
        if user.role != 'candidate' or not campaign or campaign.demo_clock is None:
            raise PermissionDenied('Dane demonstracyjne są dostępne na koncie kandydata w trybie demo.')
        User.objects.select_for_update().get(pk=user.pk)
        CandidateIdentity.objects.get_or_create(user=user, defaults={'pesel': demo_pesel(user.pk)})
        CandidateContact.objects.get_or_create(user=user,defaults={'phone':'000000000'})
        CandidateContact.objects.filter(user=user,phone='').update(phone='000000000')
        Residence.objects.get_or_create(user=user,defaults=profiles.demo_residence(0))
        services.audit(user, 'profile.demo_identity', user.id)
    elif name == 'create_application':
        return Response({'id': services.create_application(user, data['offer_id']).id})
    elif name == 'save_draft':
        services.save_draft(user, data['id'], data)
    elif name == 'submit':
        services.submit(user, data['id'], data.get('expected_round'))
    elif name == 'review':
        services.review(user, data['id'], data)
    elif name == 'photo_review':
        services.approve_photo(user, data['id'], data.get('photo_approved') is True, data.get('expected_revision'), data.get('expected_photo_id'))
    elif name == 'oath':
        app = services.take_oath(user, data['id'], data.get('accepted') is True)
        return Response({'student_number': app.student_number, 'sworn_at': app.sworn_at})
    elif name == 'batch':
        return Response(services.batch_operation(user, data.get('operation'), data.get('ids'), data, data.get('preview', False)))
    elif name == 'restart':
        return Response({'campaign_id': services.restart_campaign(user, data['campaign_id']).id})
    elif name == 'demo_scenario':
        from .demo import run_scenario
        return Response(run_scenario(user, data['campaign_id'], data.get('scenario')))
    elif name in ['confirm', 'withdraw', 'continue']:
        services.candidate_decision(user, data['id'], name)
    elif name == 'publish':
        pub = services.publish(user, data['offer_id'], str(data.get('reason', '')), data.get('correction'), data.get('expected_round'))
        return Response({'id': pub.id, 'qualified': pub.qualified_count, 'overflow': pub.overflow, 'version': pub.version,
                         'created': pub.was_created})
    elif name == 'clock':
        target = parse_datetime(str(data.get('target', '')))
        if not target or timezone.is_naive(target):
            raise ValidationError('Termin musi zawierać strefę czasową.')
        services.move_clock(user, data['campaign_id'], target)
    elif name == 'finalize':
        services.finalize(user, data['campaign_id'])
    elif name == 'read_notifications':
        user.notifications.update(read=True)
        services.audit(user, 'notifications.read', user.id)
    elif name == 'configure_offer':
        catalogue.configure_offer(user,data)
    elif name == 'create_offer':
        return Response({'id':catalogue.create_offer(user,data).id},status=201)
    elif name in ['housing_apply','housing_withdraw']:
        item = housing.change_request(user,data['campaign_id'],data.get('preferred'),withdraw=name=='housing_withdraw')
        return Response({'id':item.id if item else None})
    elif name == 'role':
        services.require_staff(user, admin=True)
        target = User.objects.select_for_update().get(pk=data['user_id'])
        role = data.get('role')
        if role not in ['candidate', 'commission', 'admin'] or target.id == user.id:
            raise ValidationError('Nie można zmienić własnej roli; wybierz poprawną rolę innego konta.')
        if target.applications.exists():
            raise ValidationError('Konto z historią kandydowania pozostaje kontem kandydata. Utwórz osobne konto pracownika.')
        old = target.role
        target.role = role
        target.save(update_fields=['role'])
        Session.objects.filter(user=target).delete()
        services.audit(user, 'account.role', target.id, before=old, after=role)
    elif name == 'totp_setup':
        user = User.objects.select_for_update().get(pk=user.pk)
        if user.totp_secret:
            raise ValidationError('Weryfikacja dwuetapowa jest już włączona.')
        user.totp_pending = pyotp.random_base32()
        user.save(update_fields=['totp_pending'])
        return Response({'secret': user.totp_pending, 'uri': pyotp.TOTP(user.totp_pending).provisioning_uri(user.email, issuer_name='Rekrutacja PK – projekt')})
    elif name == 'totp_enable':
        user = User.objects.select_for_update().get(pk=user.pk)
        if not user.totp_pending or not pyotp.TOTP(user.totp_pending).verify(str(data.get('code', ''))):
            raise ValidationError('Niepoprawny kod. Najpierw dodaj klucz do aplikacji uwierzytelniającej.')
        recovery = secrets.token_hex(16)
        user.totp_secret, user.totp_pending = user.totp_pending, ''
        user.recovery_hash = make_password(recovery)
        user.save()
        services.audit(user, 'account.totp_enabled', user.id)
        return Response({'recovery_code': recovery})
    elif name == 'totp_disable':
        user = User.objects.select_for_update().get(pk=user.pk)
        if not user.check_password(str(data.get('password', ''))):
            raise ValidationError('Podaj poprawne hasło do konta.')
        if not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(str(data.get('code', '')), valid_window=0):
            raise ValidationError('Podaj aktualny kod z aplikacji Authenticator.')
        user.totp_secret = user.totp_pending = ''
        user.totp_last_step = 0
        user.save(update_fields=['totp_secret', 'totp_pending', 'totp_last_step'])
        Session.objects.filter(user=user).exclude(pk=request.auth.pk).delete()
        services.audit(user, 'account.totp_disabled', user.id)
    else:
        raise ValidationError('Nieznana operacja.')
    return Response({'ok': True})


def validate_upload(file, kind):
    if file is None:
        raise ValidationError('Wybierz plik do przesłania.')
    if file.size > 10 * 1024 * 1024:
        raise ValidationError('Maksymalny rozmiar pliku to 10 MB.')
    ext = Path(file.name).suffix.lower()
    content = file.read()
    if kind == 'photo' and ext not in ['.png', '.jpg', '.jpeg']:
        raise ValidationError('Zdjęcie powinno być plikiem PNG lub JPG.')
    try:
        if ext == '.pdf':
            from pypdf import PdfReader
            if not content.startswith(b'%PDF-'):
                raise ValueError()
            pdf = PdfReader(io.BytesIO(content))
            if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 100:
                raise ValueError()
        elif ext in ['.png', '.jpg', '.jpeg']:
            from PIL import Image
            with Image.open(io.BytesIO(content)) as img:
                if img.format != ('PNG' if ext == '.png' else 'JPEG'):
                    raise ValueError()
                if img.width * img.height > 25000000:
                    raise ValueError()
                if kind == 'photo' and (img.width < 200 or img.height < 200):
                    raise ValueError()
                img.verify()
        else:
            raise ValueError()
    except Exception:
        if kind == 'photo':
            raise ValidationError('Zdjęcie musi mieć format PNG lub JPG, co najmniej 200 × 200 px i najwyżej 25 mln pikseli.')
        raise ValidationError('Dozwolony jest poprawny PDF (1–100 stron, bez hasła), PNG lub JPG do 25 mln pikseli.')
    file.seek(0)
    return hashlib.sha256(content).hexdigest()


@api_view(['POST'])
@transaction.atomic
def upload_profile_photo(request):
    user = request.user
    if user.role != 'candidate':
        raise PermissionDenied('Zdjęcie może dodać właściciel profilu kandydata.')
    file = request.FILES.get('file')
    digest = validate_upload(file, 'photo')
    # Same lock order as reviews and backup. The candidate row also protects across editions.
    campaign = services.current_campaign()
    if campaign:
        Campaign.objects.select_for_update().get(pk=campaign.id)
    User.objects.select_for_update().get(pk=user.id)
    previous = services.current_photo(user.id)
    if previous and previous.sha256 == digest:
        return Response(photo_data(previous))
    photo = ProfilePhoto.objects.create(user=user, file=file, original_name=Path(file.name).name[:200],
                                        sha256=digest, version=previous.version + 1 if previous else 1)
    services.audit(user, 'profile.photo_uploaded', user.id, version=photo.version)
    return Response(photo_data(photo))


@api_view(['GET'])
def download_profile_photo(request, photo_id):
    photo = ProfilePhoto.objects.get(pk=photo_id)
    user = request.user
    if user.id != photo.user_id:
        services.require_staff(user)
        if not Application.objects.filter(candidate_id=photo.user_id).exclude(status='draft').exists():
            raise PermissionDenied('Zdjęcie jest dostępne przy złożonym zgłoszeniu.')
    services.audit(user, 'document.downloaded', photo.user_id, profile_photo=photo.id)
    return FileResponse(photo.file.open('rb'), as_attachment=True, filename=photo.original_name)


def profile_document_data(doc):
    return {'id':doc.id,'kind':doc.kind,'label':doc.get_kind_display(),'name':doc.original_name,'version':doc.version,
            'url':f'/profile/document/{doc.id}'}


@api_view(['POST'])
@transaction.atomic
def upload_profile_document(request):
    user = request.user
    if user.role != 'candidate':
        raise PermissionDenied('Dokumenty dodaje właściciel profilu.')
    kind = request.data.get('kind')
    if kind not in ProfileDocument.Kind.values:
        raise ValidationError('Wybierz typ dokumentu.')
    file = request.FILES.get('file')
    digest = validate_upload(file,kind)
    campaign = services.current_campaign()
    if campaign:
        Campaign.objects.select_for_update().get(pk=campaign.id)
    User.objects.select_for_update().get(pk=user.id)
    previous = ProfileDocument.objects.filter(user=user,kind=kind).order_by('-version').first()
    if previous and previous.sha256 == digest:
        return Response(dict(profile_document_data(previous),workspace_revision=workspace_revision()))
    doc = ProfileDocument.objects.create(user=user,kind=kind,version=previous.version+1 if previous else 1,
                                         file=file,original_name=Path(file.name).name[:200],sha256=digest)
    services.audit(user,'profile.document_uploaded',user.id,kind=kind,version=doc.version)
    return Response(dict(profile_document_data(doc),workspace_revision=workspace_revision()))


@api_view(['GET'])
def download_profile_document(request, document_id):
    doc = ProfileDocument.objects.get(pk=document_id)
    if doc.user_id != request.user.id:
        raise PermissionDenied('Dokument jest dostępny w profilu właściciela.')
    return FileResponse(doc.file.open('rb'),as_attachment=True,filename=doc.original_name)


@api_view(['POST'])
def locate_residence(request):
    user = request.user
    if user.role != 'candidate':
        raise PermissionDenied('Adres jest dostępny w profilu kandydata.')
    resident = Residence.objects.filter(user=user).first()
    if not resident:
        raise ValidationError('Zapisz adres w profilu.')
    saved = {key:getattr(resident,key) for key in profiles.ADDRESS_FIELDS if key != 'apartment'}
    latitude, longitude = profiles.geocode(resident)
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.id)
        if Residence.objects.filter(user=user,**saved).update(latitude=latitude,longitude=longitude) != 1:
            raise ValidationError('Adres zmienił się. Ponownie ustal położenie.')
        services.audit(user,'profile.residence_located',user.id)
    return Response({'distance':profiles.distance_km(latitude,longitude)})


@api_view(['POST'])
@transaction.atomic
def upload(request, application_id):
    app = services.locked_application(application_id, request.user)
    kind, file = request.data.get('kind'), request.FILES.get('file')
    if kind == 'photo':
        raise ValidationError('Zdjęcie dodaje się w zakładce „Mój profil”.')
    services.check_open(app.offer, services.active_round(app.offer))
    if app.status not in ['draft', 'correction']:
        raise ValidationError('Dokumenty można dodać do szkicu lub zgłoszenia do uzupełnienia.')
    if kind not in ['education', 'fee', 'portfolio', 'bonus']:
        raise ValidationError('Wybierz typ dokumentu.')
    digest = validate_upload(file, kind)
    revision = (app.documents.filter(kind=kind).aggregate(m=Max('revision'))['m'] or 0) + 1
    doc = Document.objects.create(application=app, kind=kind, revision=revision, file=file,
                                  original_name=Path(file.name).name[:200], sha256=digest)
    services.audit(request.user, 'document.uploaded', app.public_id, kind=kind, revision=revision, hash=doc.sha256)
    app.revision += 1
    app.save(update_fields=['revision'])
    return Response({'id': doc.id})


@api_view(['GET'])
def download(request, document_id):
    doc = Document.objects.select_related('application').get(pk=document_id)
    if request.user.role == 'candidate' and doc.application.candidate_id != request.user.id:
        raise PermissionDenied('Nie masz dostępu do tego dokumentu.')
    services.audit(request.user, 'document.downloaded', doc.application.public_id, document=doc.id)
    return FileResponse(doc.file.open('rb'), as_attachment=True, filename=doc.original_name)


def csv_safe(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


@api_view(['GET'])
def export(request):
    services.require_staff(request.user)
    out = io.StringIO()
    writer = csv.writer(out, delimiter=';')
    writer.writerow(['ID zgłoszenia', 'Imię', 'Nazwisko', 'E-mail', 'Kierunek', 'Stopień', 'Tryb', 'Status kierunku'])
    qs = Application.objects.filter(status='confirmed', offer__campaign=requested_campaign(request)).select_related('candidate', 'offer__program')
    for a in qs:
        writer.writerow([csv_safe(v) for v in [a.public_id, a.candidate.first_name, a.candidate.last_name,
                         a.candidate.email, a.offer.program.name, a.offer.degree, a.offer.get_mode_display(), a.offer.get_state_display()]])
    services.audit(request.user, 'enrollment.exported', 'csv', count=qs.count())
    response = HttpResponse(('\ufeff' + out.getvalue()).encode('utf-8'), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="przyjeci.csv"'
    return response


@api_view(['GET'])
def publications(request, offer_id):
    services.require_staff(request.user)
    rows = []
    for pub in Publication.objects.filter(offer_id=offer_id).select_related('round').order_by('-round__number', '-version'):
        rows.append({'id': pub.id, 'round': pub.round.number, 'version': pub.version,
                     'published_at': pub.published_at, 'reason': pub.reason,
                     'entries': [{'rank': e.rank, 'candidate': f'{e.application.candidate.first_name} {e.application.candidate.last_name}',
                                  'score': str(e.score) if e.score is not None else None, 'decision': e.decision}
                                 for e in pub.entries.select_related('application__candidate').order_by('rank', 'id')]})
    return Response(rows)


@api_view(['GET'])
def history(request, application_id):
    app = Application.objects.get(pk=application_id)
    if request.user.role == 'candidate' and app.candidate_id != request.user.id:
        raise PermissionDenied('To zgłoszenie nie należy do Ciebie.')
    return Response([{'round': e.publication.round.number, 'version': e.publication.version,
                      'reason': e.publication.reason, 'rank': e.rank,
                      'published_at': e.publication.published_at, 'decision': e.decision,
                      'explanation': e.explanation,
                      'score': str(e.score) if e.score is not None else None}
                     for e in app.ranking_entries.select_related('publication__round').order_by('-publication__published_at')])


@api_view(['GET'])
def ranking(request, offer_id):
    return Response(services.ranking_preview(request.user, offer_id))


@api_view(['POST'])
def backup(request):
    services.require_staff(request.user, admin=True)
    from backups import make_backup
    archive = make_backup()
    services.audit(request.user, 'backup.created', archive.name)
    return FileResponse(archive.open('rb'), as_attachment=True, filename=archive.name)
