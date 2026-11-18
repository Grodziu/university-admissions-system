"""Fictitious, repeatable admission cases. Never auto-decide non-demo accounts."""
from datetime import timedelta
import hashlib
import io
from pathlib import Path
from django.db import transaction
from django.db.models import F, Q
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import *
from . import services
from .identity import demo_pesel
from .profiles import demo_residence, distance_km


def avatar_bytes():
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (360, 460), '#E7F0F8')
    draw = ImageDraw.Draw(image)
    draw.ellipse((115, 65, 245, 195), fill='#6C8BA9')
    draw.rounded_rectangle((65, 215, 295, 425), radius=90, fill='#315B80')
    draw.rectangle((0, 430, 360, 460), fill='#003571')
    draw.text((155, 440), 'DEMO', fill='white')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def prepare_samples():
    from reportlab.pdfgen import canvas

    samples = settings.DATA_DIR / 'demo-dokumenty'
    samples.mkdir(exist_ok=True)
    descriptions = {
        'swiadectwo.pdf': 'Przykladowy dokument wyksztalcenia.',
        'przelew-85zl.pdf': 'Przykladowa kwota: 85,00 PLN. Nie wykonano zadnego przelewu.',
        'przelew-50zl.pdf': 'Przykladowa kwota: 50,00 PLN. Oplata za nabor wynosi 85,00 PLN.',
        'portfolio.pdf': 'Przykladowa dokumentacja projektu do oceny portfolio.',
        'osiagniecie.pdf': 'Fikcyjny dyplom laureata etapu wojewodzkiego.',
    }
    for filename, description in descriptions.items():
        path = samples / filename
        if path.exists():
            continue
        pdf = canvas.Canvas(str(path), invariant=True)
        pdf.setFont('Helvetica-Bold', 20)
        pdf.drawString(55, 770, 'DOKUMENT DEMONSTRACYJNY')
        pdf.setFont('Helvetica', 12)
        pdf.drawString(55, 735, 'Rekrutacja PK. Fikcyjne dane do testowania projektu.')
        pdf.drawString(55, 710, description)
        pdf.save()
    photo = samples / 'zdjecie-demo.png'
    if not photo.exists():
        photo.write_bytes(avatar_bytes())
    return samples


def sample_reference(samples, name):
    content = (samples / name).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    relative = Path('demo-fixtures') / f'{digest}{Path(name).suffix}'
    path = Path(settings.MEDIA_ROOT) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    return {'original_name': name, 'sha256': digest, 'file': relative.as_posix()}


DEMO_PEOPLE = [('przyjety', 'Michał', 'Zieliński'), ('rezerwa', 'Klara', 'Maj'),
               ('odrzucony', 'Jan', 'Lis'), ('bezpotwierdzenia', 'Oskar', 'Wójcik')]
FIRST_NAMES = ('Alicja', 'Bartosz', 'Julia', 'Filip', 'Natalia', 'Jakub', 'Zuzanna', 'Antoni', 'Wiktoria', 'Adam', 'Laura', 'Leon')
FAMILY_NAMES = ('Nowak', 'Kowalczyk', 'Wójcik', 'Król', 'Mazur', 'Kaczmarek', 'Dudek', 'Zając', 'Urban', 'Lis', 'Wrona', 'Golba')


@transaction.atomic
def populate_campaign(campaign, actor):
    if campaign.demo_scenario:
        return
    if campaign.offers.filter(applications__isnull=False).exists():
        raise ValidationError('Ten nabór ma już zgłoszenia. Zestaw danych można wczytać do pustej nowej edycji.')
    anna = User.objects.get(email='kandydat@demo.local')
    samples = prepare_samples()
    artifacts = {name: sample_reference(samples, name) for name in
                 ['zdjecie-demo.png', 'swiadectwo.pdf', 'przelew-85zl.pdf', 'przelew-50zl.pdf', 'portfolio.pdf', 'osiagniecie.pdf']}
    personas = {}
    for key, first, last in DEMO_PEOPLE:
        email = key + '@demo.local'
        person, _ = User.objects.get_or_create(username=email, defaults={
            'email': email, 'first_name': first, 'last_name': last,
            'role': 'candidate', 'is_demo': True, 'password': anna.password
        })
        for subject, level, value in [('matematyka', 'basic', 90), ('matematyka', 'extended', 92), ('informatyka', 'extended', 81)]:
            ExamResult.objects.get_or_create(user=person, subject=subject, level=level, defaults={'value': value})
        AcademicAverage.objects.get_or_create(user=person, defaults={'value': '4.20'})
        Diploma.objects.get_or_create(user=person, defaults={'title': 'inżynier'})
        personas[key] = person
    featured = {0: anna, 1: personas['przyjety'], 2: personas['bezpotwierdzenia'],
                32: personas['rezerwa'], 35: personas['odrzucony']}
    rounds = {item.degree: item for item in campaign.rounds.filter(number=1)}
    offers = campaign.offers.select_related('program').prefetch_related('allowed_subjects').order_by('id')
    plan = []
    fixtures = []
    for offer in offers:
        main_offer = (offer.program.name, offer.degree, offer.mode) == ('Informatyka', 'I', 'S')
        count = max(offer.minimum + 2, 36) if main_offer else min(offer.capacity, offer.minimum + 2 + offer.id % 4)
        for index in range(count):
            person = featured.get(index) if main_offer else None
            if person is None:
                serial = len(plan) + 1
                email = f'demo.c{campaign.id}.{serial:04}@demo.local'
                person = User(username=email, email=email, first_name=FIRST_NAMES[serial % len(FIRST_NAMES)],
                              last_name=FAMILY_NAMES[(serial // 3) % len(FAMILY_NAMES)], is_active=False, is_demo=True)
                person.set_unusable_password()
                fixtures.append(person)
            plan.append((offer, person, index, main_offer))
    User.objects.bulk_create(fixtures, batch_size=500)

    now = timezone.now()
    elapsed = max(campaign.now() - campaign.start, timedelta(0))
    applications = []
    documents_by_app = []
    photos = []
    people = {person.pk for _, person, _, _ in plan}
    with_photo = set(ProfilePhoto.objects.filter(user_id__in=people).values_list('user_id', flat=True))
    CandidateIdentity.objects.bulk_create(
        [CandidateIdentity(user_id=pk, pesel=demo_pesel(pk)) for pk in people], ignore_conflicts=True, batch_size=500)
    # The application role writes through the view; only new people need a contact.
    contacts = set(CandidateContact.objects.filter(user_id__in=people).values_list('user_id', flat=True))
    CandidateContact.objects.bulk_create(
        [CandidateContact(user_id=pk, phone='000000000') for pk in people - contacts], batch_size=500)
    Residence.objects.bulk_create([Residence(user_id=pk,**demo_residence(pk)) for pk in people],
                                  ignore_conflicts=True,batch_size=500)
    homes = Residence.objects.in_bulk(people)
    shared_files = {}
    housing_requests = []
    for serial, (offer, person, index, main_offer) in enumerate(plan, 1):
        case = {2: 'expire', 34: 'correction', 35: 'reject'}.get(index, 'accept') if main_offer else 'accept'
        pending = index < 4 and main_offer or index < 2 and offer.program.name in ('Architektura', 'Informatyka')
        status = {'reject': 'rejected', 'correction': 'correction'}.get(case, 'submitted' if pending else 'verified')
        p1 = 97 - index if index < 29 else 68 if index in [29, 30] else 40
        subject = next((rule.subject for rule in offer.allowed_subjects.all() if rule.subject != 'matematyka'), 'matematyka')
        snapshot = {'first_name': person.first_name, 'last_name': person.last_name, 'email': person.email,
                    'rule_version': offer.rule_version, 'demo_case': case, 'M': '90', 'P1': str(p1), 'P2': '55',
                    'P1_source': subject, 'P2_source': 'matematyka', 'average': f'{max(2,4.95-index*.05):.2f}', 'diploma': 'inżynier'}
        if person == anna:
            snapshot.update(services.input_snapshot(Application(candidate=person, offer=offer)))
        bonus = index == 3 and main_offer
        if person.pk not in with_photo:
            photos.append(ProfilePhoto(user=person, version=1, approved_at=now if status == 'verified' else None,
                                       approved_by=actor if status == 'verified' else None, **artifacts['zdjecie-demo.png']))
            with_photo.add(person.pk)
        applications.append(Application(
            candidate=person, offer=offer, round=rounds[offer.degree], status=status,
            submitted_at=campaign.start + elapsed * (serial / len(plan)), input_snapshot=snapshot,
            bonus_claimed=bonus, payment_approved=status == 'verified',
            payment_amount=offer.fee if status == 'verified' else 50 if case == 'reject' else None,
            portfolio_grade='accepted' if status == 'verified' and offer.portfolio_required else 'none',
            reviewed_by=actor if status == 'verified' else None,
            feedback='Na potwierdzeniu widnieje 50 zł.' if case == 'reject' else 'Potrzebny czytelny skan świadectwa.' if case == 'correction' else '',
        ))
        files = {'education': 'swiadectwo.pdf', 'fee': 'przelew-50zl.pdf' if case == 'reject' else 'przelew-85zl.pdf'}
        if offer.portfolio_required:
            files['portfolio'] = 'portfolio.pdf'
        if bonus:
            files['bonus'] = 'osiagniecie.pdf'
        for kind, name in files.items():
            if kind != 'fee':
                profile_kind = 'diploma' if kind == 'education' and offer.degree != 'I' else kind
                shared_files[(person.id,profile_kind)] = name
        home = homes.get(person.id)
        if person != anna and offer.degree in ['I','II'] and status != 'rejected' and serial % 4 != 0 and home and home.latitude is not None:
            housing_requests.append(HousingApplication(
                candidate=person,campaign=campaign,preferred_id='DS2' if serial % 5 else 'DS3',
                distance_km=distance_km(home.latitude,home.longitude)))
        documents_by_app.append(files)
    ProfilePhoto.objects.bulk_create(photos, batch_size=500)
    ProfileDocument.objects.bulk_create([
        ProfileDocument(user_id=pk,kind=kind,version=1,**artifacts[name])
        for (pk,kind),name in shared_files.items()
    ],ignore_conflicts=True,batch_size=500)
    Application.objects.bulk_create(applications, batch_size=500)
    Document.objects.bulk_create([
        Document(application=app, kind=kind, revision=1, **artifacts[name])
        for app, files in zip(applications, documents_by_app) for kind, name in files.items()
    ], batch_size=500)
    HousingApplication.objects.bulk_create(housing_requests,ignore_conflicts=True,batch_size=500)
    campaign.demo_scenario = 'all-offers'
    campaign.save(update_fields=['demo_scenario'])
    services.audit(actor, 'demo.dataset_created', campaign.id, applications=len(plan))


def prepare_demo_applications(actor, campaign):
    rows = Application.objects.filter(offer__campaign=campaign, candidate__is_demo=True,
                                      offer__state='open', round__end__gt=campaign.now(),
                                      status__in=['submitted','correction']).select_related('offer')
    for app in rows:
        if app.input_snapshot.get('demo_case') == 'correction':
            services.review(actor, app.id, {'decision':'reject','feedback':'Scenariusz demonstracyjny: brak czytelnego dokumentu wykształcenia.'})
            continue
        if not services.current_photo(app.candidate_id):
            ProfilePhoto.objects.create(user_id=app.candidate_id, version=1,
                                        **sample_reference(prepare_samples(), 'zdjecie-demo.png'))
        services.review(actor, app.id, {'decision':'verify','payment_matches':True,'photo_approved':True,
            'portfolio_grade':'accepted' if app.offer.portfolio_required else 'none',
            'bonus_category':'regional_winner' if app.bonus_claimed else '',
            'feedback':'Dokumenty sprawdzone w scenariuszu demonstracyjnym.'})


def retry_demo_candidates(actor, campaign):
    now = campaign.now()
    for round_ in campaign.rounds.filter(start__lte=now, application_end__gt=now):
        earlier = (Application.objects.filter(offer__campaign=campaign, offer__degree=round_.degree,
                                             offer__state='open', candidate__is_demo=True, round__number__lt=round_.number,
                                             status__in=['expired', 'waitlist'], payment_approved=True)
                   .exclude(input_snapshot__demo_case='expire'))
        changed = list(earlier.values_list('public_id', flat=True))
        earlier.update(round=round_, status='verified', revision=F('revision') + 1,
                       feedback='Ponowny udział w kolejnej turze demonstracyjnej.')
        AuditEvent.objects.bulk_create([AuditEvent(actor=actor, action='demo.application_retried', entity=str(ident),
                                                 details={'round': round_.number}) for ident in changed], batch_size=500)


def settle_current_stage(actor, campaign):
    now = campaign.now()
    retry_demo_candidates(actor, campaign)
    prepare_demo_applications(actor, campaign)
    for round_ in campaign.rounds.filter(application_end__lte=now, end__gt=now):
        offer_ids = (Application.objects.filter(round=round_, status='verified')
                     .values_list('offer_id', flat=True).distinct())
        for offer_id in offer_ids:
            services.publish(actor, offer_id)
    awaiting = (Application.objects.filter(offer__campaign=campaign, offer__state='open', status='qualified',
                                          candidate__is_demo=True, round__end__gt=now)
                .exclude(input_snapshot__demo_case='expire'))
    confirmed = list(awaiting.values_list('public_id', 'candidate_id'))
    # The scenario holds the campaign lock. Same qualification, deadline and offer
    # checks as candidate_decision(), with one update for the simulated candidates.
    awaiting.update(status='confirmed', revision=F('revision') + 1)
    AuditEvent.objects.bulk_create([
        AuditEvent(actor_id=actor_id, action=event, entity=str(ident))
        for ident, candidate_id in confirmed
        for actor_id, event in [(candidate_id, 'application.confirm'), (actor.id, 'demo.place_confirmed')]
    ], batch_size=500)


def scenario_result(campaign):
    launched = campaign.offers.filter(state='launched').count()
    anna_apps = list(Application.objects.filter(offer__campaign=campaign, candidate__email='kandydat@demo.local')
                     .select_related('offer__program', 'offer__campaign').order_by('-submitted_at', 'pk'))
    anna = next((app for app in anna_apps if app.status == 'confirmed'), None)
    anna = anna or next((app for app in anna_apps if app.submitted_at), None)
    anna = anna or next(iter(anna_apps), None)
    photo = services.current_photo(anna.candidate_id) if anna else None
    has_pesel = bool(anna and CandidateIdentity.objects.filter(user_id=anna.candidate_id).exists())
    qualified = [app for app in anna_apps if not app.sworn_at and not services.oath_problem(app, photo, has_pesel)]
    if qualified:
        anna = qualified[0]
    can_oath = bool(qualified)
    if can_oath:
        detail = f'Anna może złożyć ślubowanie na kierunku {anna.offer.program.name}.'
    elif anna and anna.sworn_at:
        detail = f'Anna złożyła ślubowanie na kierunku {anna.offer.program.name}.'
    elif anna:
        detail = f'Anna · {anna.offer.program.name}: {anna.get_status_display().lower()}.'
        if anna.status == 'confirmed' and anna.offer.state == 'launched' and not anna.sworn_at:
            detail += ' ' + services.oath_problem(anna, photo, has_pesel)
    else:
        detail = 'W tej edycji Anna nie złożyła zgłoszenia.'
    return {'message': f'Nabór zakończony. Uruchomiono {launched} z {campaign.offers.count()} wariantów. {detail}',
            'launched': launched, 'anna_can_oath': can_oath}


@transaction.atomic
def run_scenario(actor, campaign_id, scenario):
    services.require_staff(actor, admin=True)
    if scenario not in ['planning', 'populate', 'ready', 'step', 'final']:
        raise ValidationError('Wybierz dostępny scenariusz demonstracyjny.')
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    if campaign.closed and scenario == 'final' and campaign.demo_clock is not None:
        return scenario_result(campaign)
    if campaign.closed or campaign.demo_clock is None:
        raise ValidationError('Scenariusze są dostępne w otwartej edycji demonstracyjnej.')
    if scenario == 'planning':
        if campaign.offers.filter(Q(applications__isnull=False)|Q(publications__isnull=False)).exists() or campaign.housing_requests.exists():
            raise ValidationError('Przygotowanie katalogu jest dostępne w pustej edycji demonstracyjnej.')
        campaign.demo_clock = campaign.start - timedelta(days=1)
        campaign.save(update_fields=['demo_clock'])
        services.audit(actor,'demo.planning',campaign.id)
        return {'message':'Edycja jest przed startem zapisów. W „Kierunki i listy” możesz zmieniać i dodawać oferty.'}
    if scenario == 'populate':
        if campaign.now() < campaign.start:
            services.move_clock(actor,campaign.id,campaign.start+timedelta(days=3))
            campaign.refresh_from_db()
        populate_campaign(campaign, actor)
        return {'message':'Wczytano różne przypadki kandydatów: do weryfikacji, uzupełnienia, odrzucenia, przyjęcia i rezerwy.'}
    if Application.objects.filter(offer__campaign=campaign, candidate__is_demo=False).exclude(status__in=['draft','withdrawn','rejected']).exists():
        raise ValidationError('Nabór zawiera aktywne zgłoszenia spoza kont demonstracyjnych. Obsłuż go ręcznie albo wybierz pustą edycję demo.')
    if scenario == 'ready':
        prepare_demo_applications(actor, campaign)
        return {'message': 'Dokumenty demonstracyjne oceniono. W „Kierunki i listy” zobaczysz, kiedy każdą listę można opublikować.'}
    moments = sorted({moment for r in campaign.rounds.all() for moment in (r.start,r.application_end,r.end)})
    future = [moment for moment in moments if moment > campaign.now()]
    settle_current_stage(actor, campaign)
    for moment in future[:1] if scenario == 'step' else future:
        services.move_clock(actor, campaign.id, moment)
        campaign.refresh_from_db()
        if campaign.closed:
            break
        settle_current_stage(actor, campaign)
    services.audit(actor, 'demo.scenario_completed', campaign.id, scenario=scenario)
    if campaign.closed:
        return scenario_result(campaign)
    stamp = timezone.localtime(campaign.now()).strftime('%d.%m.%Y, %H:%M')
    return {'message': f'Scenariusz przeszedł do {stamp}. W „Kierunki i listy” widać opublikowane wyniki i potwierdzone miejsca.'}
