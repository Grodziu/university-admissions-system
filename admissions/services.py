"""Transactional application use cases. Lock order: campaign → offer → application."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlparse
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import (User, Campaign, Round, Offer, Application, Document, AcademicAverage,
                     Diploma, Publication, RankingEntry, AuditEvent, Notification, CandidateIdentity, ProfilePhoto)
from .domain import STRATEGIES, select_with_ties, RuleError
from .policies import BONUS_BY_CODE, OATH_TEXT
from .profiles import attach_documents, profile_complete
from .campus import ACCOUNTS, ADAPCIAK, DELTA, DEPARTMENT_PLANS, SCHEDULES, WELCOME_NOTIFICATION, WELCOME_OATH_INSTRUCTION
from .mailing import record_notifications


def current_campaign():
    return Campaign.objects.order_by('-start', '-id').first()


def submission_block_reason(offer):
    if offer.campaign.closed or offer.state != 'open':
        return 'Ten nabór został zakończony. Wybierz nową edycję rekrutacji.'
    now = offer.campaign.now()
    current = active_round(offer)
    if current and now < current.application_end:
        return ''
    next_round = next((r for r in offer.campaign.rounds.all() if r.degree == offer.degree and r.start > now), None)
    message = ('Zapisy w tej turze są już zamknięte. Teraz trwa weryfikacja, publikacja wyników i potwierdzanie miejsc.'
               if current else 'Trwa przerwa w przyjmowaniu zgłoszeń.')
    if next_round:
        message += f' Tura {next_round.number} rozpocznie się {timezone.localtime(next_round.start):%d.%m.%Y o %H:%M}.'
    else:
        message += ' W tej edycji nie ma już następnej tury.'
    return message


def require_staff(user, admin=False):
    allowed = ['admin'] if admin else ['admin', 'commission']
    if not user or user.role not in allowed:
        raise PermissionDenied('Ta czynność wymaga uprawnień administratora.' if admin else 'Ta czynność wymaga uprawnień komisji.')


def audit(actor, action, entity, **details):
    AuditEvent.objects.create(actor=actor, action=action, entity=str(entity), details=details)


def notify(user, title, message):
    record_notifications([Notification(user=user, title=title, message=message)])


def student_card_period(campaign):
    year = timezone.localtime(campaign.start).year
    return date(year, 10, 1), date(year + 1, 4, 1) - timedelta(days=1)


def active_round(offer):
    now = offer.campaign.now()
    if 'rounds' in getattr(offer.campaign, '_prefetched_objects_cache', {}):
        return next((r for r in offer.campaign.rounds.all() if r.degree == offer.degree and r.start <= now < r.end), None)
    return Round.objects.filter(campaign=offer.campaign, degree=offer.degree, start__lte=now, end__gt=now).first()


def check_open(offer, round_):
    reason = submission_block_reason(offer)
    if reason:
        raise ValidationError(reason)
    if not round_ or not round_.start <= offer.campaign.now() < round_.application_end:
        raise ValidationError('Termin składania zgłoszeń jeszcze się nie rozpoczął.')


def check_review_revision(app, expected_revision):
    if expected_revision is not None and expected_revision != app.revision:
        raise ValidationError('Zgłoszenie zmieniło się od otwarcia okna. Zamknij je, odśwież widok i ponownie sprawdź dokumenty.')


def check_round_number(round_, expected_round):
    if expected_round is not None and (not round_ or round_.number != expected_round):
        raise ValidationError('Serwer przeszedł do innej tury. Odśwież widok przed ponowieniem operacji.')


def current_photo(user_id):
    return ProfilePhoto.objects.filter(user_id=user_id).first()


def accept_photo(photo, actor):
    if not photo.approved_at:
        photo.approved_at = timezone.now()
        photo.approved_by = actor
        photo.save(update_fields=['approved_at', 'approved_by'])
        audit(actor, 'profile.photo_approved', photo.user_id, version=photo.version)
    return photo


def check_photo_version(photo, data):
    if 'expected_photo_id' in data and data['expected_photo_id'] != (photo.pk if photo else None):
        raise ValidationError('Kandydat zmienił zdjęcie. Odśwież widok i obejrzyj nową wersję.')


def locked_offer(offer_id):
    campaign_id = Offer.objects.values_list('campaign_id', flat=True).get(pk=offer_id)
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    offer = Offer.objects.select_for_update().select_related('program').get(pk=offer_id)
    offer.campaign = campaign
    return offer


def locked_application(app_id, user, staff=False):
    offer_id = Application.objects.values_list('offer_id', flat=True).get(pk=app_id)
    offer = locked_offer(offer_id)
    app = Application.objects.select_for_update().select_related('candidate', 'round').get(pk=app_id)
    app.offer = offer
    if staff:
        require_staff(user)
    elif app.candidate_id != user.id or user.role != 'candidate':
        raise PermissionDenied('To zgłoszenie nie należy do Ciebie.')
    return app


def input_snapshot(app):
    user, offer = app.candidate, app.offer
    if not user.first_name.strip() or not user.last_name.strip():
        raise ValidationError('Uzupełnij imię i nazwisko w profilu.')
    base = {'first_name': user.first_name, 'last_name': user.last_name,
            'email': user.email, 'rule_version': offer.rule_version}
    if offer.degree == 'I':
        exams = list(user.exam_results.all())
        math = next((e for e in exams if e.subject == 'matematyka' and e.level == 'basic'), None)
        if not math:
            raise ValidationError('Uzupełnij wynik z matematyki na poziomie podstawowym.')
        allowed = set(offer.allowed_subjects.values_list('subject', flat=True))
        professions = set(offer.allowed_professions.values_list('name', flat=True))
        eligible = [e for e in exams if (e.level == 'extended' and e.subject in allowed) or
                    (e.level == 'technical' and e.subject in professions)]
        eligible.sort(key=lambda e: (-e.value, e.subject, e.level))
        # One subject/qualification can only fill one component.
        unique = []
        for e in eligible:
            if e.subject not in [r.subject for r in unique]:
                unique.append(e)
        if not unique:
            raise ValidationError('Dodaj co najmniej jeden dopuszczony przedmiot rozszerzony lub wynik kwalifikacji technika.')
        base.update(M=str(math.value), P1=str(unique[0].value), P2=str(unique[1].value if len(unique) > 1 else 0),
                    P1_source=unique[0].subject, P2_source=unique[1].subject if len(unique) > 1 else 'brak',
                    exams=[{'subject': e.subject, 'level': e.level, 'value': str(e.value)} for e in exams])
    else:
        diploma = Diploma.objects.filter(user=user).first()
        if not diploma or not diploma.title.strip():
            raise ValidationError('Podaj tytuł uzyskany po ukończeniu studiów co najmniej I stopnia.')
        base['diploma'] = diploma.title
        if offer.degree == 'II':
            average = AcademicAverage.objects.filter(user=user).first()
            if not average:
                raise ValidationError('Uzupełnij średnią ze studiów I stopnia (2,00–5,00).')
            base['average'] = str(average.value)
    return base


@transaction.atomic
def create_application(user, offer_id):
    if user.role != 'candidate':
        raise PermissionDenied('Zgłoszenia składa kandydat.')
    offer = locked_offer(offer_id)
    round_ = active_round(offer)
    existing = Application.objects.filter(candidate=user, offer=offer).first()
    if existing:
        return existing
    check_open(offer, round_)
    app = Application.objects.create(candidate=user, offer=offer, round=round_)
    audit(user, 'application.created', app.public_id)
    return app


@transaction.atomic
def save_draft(user, app_id, data):
    app = locked_application(app_id, user)
    check_open(app.offer, active_round(app.offer))
    if app.status not in ['draft', 'correction']:
        raise ValidationError('Złożonego zgłoszenia nie można zmienić bez cofnięcia do uzupełnienia przez komisję.')
    url = str(data.get('portfolio_url', app.portfolio_url)).strip()
    if url and (urlparse(url).scheme != 'https' or not urlparse(url).hostname or len(url) > 500):
        raise ValidationError('Link do portfolio musi być poprawnym adresem HTTPS.')
    app.portfolio_url = url
    app.bonus_claimed = bool(data.get('bonus_claimed', app.bonus_claimed))
    app.save()
    return app


@transaction.atomic
def submit(user, app_id, expected_round=None):
    app = locked_application(app_id, user)
    if app.status == 'submitted':
        return app  # idempotent retry
    if app.status not in ['draft', 'correction']:
        raise ValidationError('Tego zgłoszenia nie można teraz złożyć.')
    round_ = active_round(app.offer)
    check_open(app.offer, round_)
    check_round_number(round_, expected_round)
    if not CandidateIdentity.objects.filter(user=user).exists():
        raise ValidationError('Zapisz PESEL w zakładce „Mój profil”, a potem wróć do zgłoszenia.')
    if not profile_complete(user):
        raise ValidationError('Uzupełnij telefon i adres zamieszkania w zakładce „Mój profil”.')
    attach_documents(app)
    kinds = set(app.documents.values_list('kind', flat=True))
    if not {'education', 'fee'} <= kinds:
        missing = []
        if 'education' not in kinds:
            missing.append('Dodaj świadectwo maturalne w profilu.' if app.offer.degree == 'I'
                           else 'Dodaj dyplom ukończenia studiów w profilu.')
        if 'fee' not in kinds:
            missing.append('Dodaj potwierdzenie przelewu w tym zgłoszeniu.')
        raise ValidationError(' '.join(missing))
    if app.offer.photo_required and current_photo(user.pk) is None:
        raise ValidationError('Dodaj zdjęcie w zakładce „Mój profil”. Pojawi się we wszystkich Twoich zgłoszeniach.')
    if app.offer.portfolio_required and 'portfolio' not in kinds and not app.portfolio_url:
        raise ValidationError('Ten kierunek wymaga portfolio lub linku do projektu.')
    if app.bonus_claimed and 'bonus' not in kinds:
        raise ValidationError('Do premii do 50 punktów wymagane jest potwierdzenie osiągnięcia.')
    app.input_snapshot = input_snapshot(app)
    app.round = round_
    app.submitted_at = timezone.now()
    app.status = 'submitted'
    app.payment_approved = False
    app.bonus_approved = False
    app.bonus_points = 0
    app.bonus_category = ''
    app.portfolio_grade = 'none'
    app.revision += 1
    app.save()
    audit(user, 'application.submitted', app.public_id, revision=app.revision, round=round_.number)
    notify(user, 'Zgłoszenie zostało złożone', f'{app.offer.program.name}: komisja sprawdzi dokumenty i opłatę.')
    return app


@transaction.atomic
def review(user, app_id, data):
    app = locked_application(app_id, user, staff=True)
    check_review_revision(app, data.get('expected_revision'))
    if app.offer.campaign.closed or app.offer.campaign.now() >= app.round.end:
        raise ValidationError('Tura została zamknięta na serwerze. Odśwież widok zgłoszeń.')
    if app.status not in ['submitted', 'correction', 'verified', 'rejected']:
        raise ValidationError('Można oceniać zgłoszenie przed publikacją listy.')
    if Publication.objects.filter(offer=app.offer, round=app.round).exists():
        raise ValidationError('Lista tej tury jest już opublikowana. Zapisz korektę jako nową wersję publikacji.')
    action = data.get('decision')
    feedback = str(data.get('feedback', '')).strip()
    if action not in ['verify', 'correct', 'reject']:
        raise ValidationError('Nieznana decyzja komisji.')
    if action in ['correct', 'reject'] and not feedback:
        raise ValidationError('Podaj konkretną przyczynę i sposób uzupełnienia.')
    if action == 'correct' and app.offer.campaign.now() >= app.round.application_end:
        raise ValidationError('Termin uzupełnienia minął. Zgłoszenie można odrzucić z uzasadnieniem.')
    from .domain import number
    entered = data.get('payment_amount')
    if data.get('payment_matches') is True and entered not in [None, ''] and number(entered, 0, 100000) != app.offer.fee:
        raise ValidationError(f'Zaznaczono zgodność z opłatą {app.offer.fee} zł, ale wpisano inną kwotę.')
    if action == 'verify':
        if data.get('payment_matches') is False:
            raise ValidationError('Zaznacz zgodność kwoty przelewu. Przy innej kwocie wybierz „Do uzupełnienia” lub „Odrzuć” i podaj przyczynę.')
        amount = app.offer.fee if data.get('payment_matches') is True else number(data.get('payment_amount'), 0, 100000)
        if amount != app.offer.fee:
            raise ValidationError(f'Potwierdzona kwota musi wynosić {app.offer.fee} zł.')
        if not app.documents.filter(kind='fee').exists() or not app.documents.filter(kind='education').exists():
            raise ValidationError('Brakuje potwierdzenia opłaty lub dokumentu wykształcenia.')
        portfolio = data.get('portfolio_grade', 'none')
        if portfolio not in ['none', 'accepted', 'excellent', 'rejected']:
            raise ValidationError('Niepoprawna ocena portfolio.')
        has_portfolio = app.documents.filter(kind='portfolio').exists() or app.portfolio_url
        if portfolio in ['accepted', 'excellent'] and not has_portfolio:
            raise ValidationError('Brak portfolio do oceny.')
        if app.offer.portfolio_required and portfolio not in ['accepted', 'excellent']:
            raise ValidationError('Wymagane portfolio musi zostać zaakceptowane.')
        if portfolio == 'excellent' and not app.offer.portfolio_bonus:
            raise ValidationError('Ta oferta nie przewiduje wyróżnienia portfolio.')
        category = data.get('bonus_category', 'legacy50' if data.get('bonus_approved') and app.offer.rule_version == '2027.1' else '')
        if category == 'legacy50' and app.offer.rule_version == '2027.1':
            points = 50
        elif category in BONUS_BY_CODE:
            points = BONUS_BY_CODE[category]['points']
        else:
            raise ValidationError('Wybierz osiągnięcie z katalogu premii.')
        if 'bonus_points' in data and number(data['bonus_points'], 0, 50) != points:
            raise ValidationError('Punkty muszą odpowiadać wybranemu osiągnięciu.')
        bonus = points > 0
        if bonus and (not app.bonus_claimed or not app.documents.filter(kind='bonus').exists() or app.offer.degree != 'I'):
            raise ValidationError('Brak podstaw do przyznania premii.')
        app.payment_amount, app.payment_approved = amount, True
        app.portfolio_grade, app.bonus_approved = portfolio, bonus
        app.bonus_category, app.bonus_points = category, points
        photo = current_photo(app.candidate_id)
        check_photo_version(photo, data)
        if app.offer.photo_required and not photo:
            raise ValidationError('Brak zdjęcia w profilu kandydata.')
        if photo and not photo.approved_at and data.get('photo_approved') is True:
            accept_photo(photo, user)
        elif photo and not photo.approved_at and app.offer.photo_required:
            raise ValidationError('Sprawdź zdjęcie z profilu i zaznacz jego akceptację.')
        app.status = 'verified'
        calculate(app)
    else:
        app.status = 'correction' if action == 'correct' else 'rejected'
        app.payment_approved = False
        if data.get('payment_amount') not in [None, '']:
            app.payment_amount = number(data['payment_amount'], 0, 100000)
            feedback = f'Odczytana kwota: {app.payment_amount:.2f} zł; wymagana: {app.offer.fee:.2f} zł. ' + feedback
    app.feedback = feedback
    app.reviewed_by = user
    app.revision += 1
    app.save()
    audit(user, f'application.{action}', app.public_id, reason=feedback, revision=app.revision,
          bonus_points=app.bonus_points, bonus_category=app.bonus_category)
    notify(app.candidate, 'Weryfikacja zgłoszenia', f'{app.offer.program.name}: {app.get_status_display()}. {feedback}')
    return app


def calculate(app):
    data = dict(app.input_snapshot)
    data.update(bonus_approved=app.bonus_approved, bonus_points=app.bonus_points,
                excellent_portfolio=app.offer.portfolio_bonus and app.portfolio_grade == 'excellent',
                submitted_at=app.submitted_at.isoformat() if app.submitted_at else None)
    return STRATEGIES[app.offer.degree].calculate(data)


def publication_status(offer, round_, counts, publication=None):
    if offer.campaign.closed or offer.state != 'open':
        return 'closed', 'Nabór zakończony.'
    if not round_:
        return 'inactive', 'Brak aktywnej tury.'
    if publication:
        return 'published', f'Wyniki opublikowane · tura {round_.number}'
    if offer.campaign.now() < round_.application_end:
        opens = timezone.localtime(round_.application_end).strftime('%d.%m, %H:%M')
        return 'accepting', f'Zapisy trwają. Publikacja od {opens} · tura {round_.number}.'
    pending = counts.get('submitted', 0) + counts.get('correction', 0)
    if pending:
        return 'review', f'Dokończ weryfikację ({pending}) · tura {round_.number}.'
    if not counts.get('verified'):
        return 'empty', 'Brak zweryfikowanych kandydatów w tej turze.'
    return 'ready', f'Możesz opublikować wyniki · tura {round_.number}.'


@transaction.atomic
def publish(user, offer_id, reason='', correction=None, expected_round=None, reject_existing=False):
    require_staff(user)
    offer = locked_offer(offer_id)
    round_ = active_round(offer)
    check_round_number(round_, expected_round)
    if not round_ or offer.campaign.now() < round_.application_end or offer.state != 'open':
        raise ValidationError('Listę można opublikować po zamknięciu zgłoszeń i przed końcem tury.')
    previous = Publication.objects.filter(offer=offer, round=round_).order_by('-version').first()
    if previous and not correction:
        if reject_existing:
            raise ValidationError(f'Wyniki dla tury {round_.number} są już opublikowane.')
        previous.was_created = False
        return previous
    if previous and not reason.strip():
        raise ValidationError('Nowa wersja publikacji wymaga przyczyny korekty.')
    if Application.objects.filter(offer=offer, round=round_, status__in=['submitted', 'correction']).exists():
        raise ValidationError('Najpierw rozpatrz wszystkie zgłoszenia oczekujące na weryfikację lub uzupełnienie.')
    if correction:
        if not previous:
            raise ValidationError('Nie ma opublikowanej listy do korekty.')
        app = Application.objects.select_for_update().get(pk=correction['application_id'], offer=offer, round=round_)
        if app.status not in ['qualified', 'waitlist', 'confirmed']:
            raise ValidationError('Korygować można wynik uczestnika opublikowanego rankingu.')
        # Corrections concern verified numeric evidence, not a free-form replacement of decisions.
        fields = ['M', 'P1', 'P2'] if offer.degree == 'I' else ['average'] if offer.degree == 'II' else []
        from .domain import number
        for field in fields:
            if field in correction:
                app.input_snapshot[field] = str(number(correction[field], 2 if field == 'average' else 0, 5 if field == 'average' else 100))
        if not fields:
            raise ValidationError('Kolejność zgłoszeń podyplomowych nie podlega ręcznemu przestawianiu.')
        app.revision += 1
        app.save()
    earlier = Application.objects.filter(offer=offer, status='confirmed').exclude(round=round_).count()
    available = max(0, offer.capacity - earlier)
    apps = list(Application.objects.select_for_update().filter(offer=offer, round=round_, status__in=['verified', 'qualified', 'waitlist', 'confirmed']))
    if not apps and not previous:
        raise ValidationError('Brak zweryfikowanych kandydatów w tej turze.')
    for app in apps:
        app.offer = offer
    rows = [(a.id, calculate(a), a.submitted_at) for a in apps]
    ordered, selected = select_with_ties(rows, available, offer.degree)
    by_id = {a.id: a for a in apps}
    cutoff = min((result.score for i, result, _ in ordered if i in selected), default=None) if offer.degree != 'PG' else None
    pub = Publication.objects.create(offer=offer, round=round_, author=user, version=previous.version + 1 if previous else 1,
                                     reason=reason, cutoff=cutoff, qualified_count=len(selected), available_places=available,
                                     overflow=max(0, len(selected) - available), rule={'version': offer.rule_version, 'degree': offer.degree, 'capacity': offer.capacity, 'minimum': offer.minimum})
    documents = defaultdict(list)
    for document in Document.objects.filter(application_id__in=by_id).values('application_id', 'kind', 'revision', 'sha256'):
        documents[document.pop('application_id')].append(document)
    entries, notifications = [], []
    rank, last_score = 0, object()
    for index, (ident, result, _) in enumerate(ordered, 1):
        app = by_id[ident]
        if offer.degree == 'PG' or result.score != last_score:
            rank = index
        last_score = result.score
        decision = 'qualified' if ident in selected else 'waitlist'
        evidence = dict(result.explanation, input=app.input_snapshot, revision=app.revision, documents=documents[ident])
        entries.append(RankingEntry(publication=pub, application=app, rank=rank, score=result.score,
                                    decision=decision, explanation=evidence))
        # A corrected ranking can revoke a confirmed place; the event is explicit and notified.
        app.status = 'confirmed' if app.status == 'confirmed' and decision == 'qualified' else decision
        notifications.append(Notification(user_id=app.candidate_id, title='Opublikowano wyniki',
                             message=f'{offer.program.name}: {app.get_status_display()}. Wersja listy {pub.version}. {reason}'))
    RankingEntry.objects.bulk_create(entries, batch_size=250)
    Application.objects.bulk_update(apps, ['status'], batch_size=250)
    record_notifications(notifications)
    audit(user, 'ranking.published', pub.id, offer=offer.id, round=round_.number, version=pub.version, reason=reason, overflow=pub.overflow)
    pub.was_created = True
    return pub


@transaction.atomic
def candidate_decision(user, app_id, action):
    app = locked_application(app_id, user)
    if action == 'confirm':
        if app.status == 'confirmed':
            return app
        if app.status != 'qualified' or app.offer.campaign.now() >= app.round.end or app.offer.state != 'open':
            raise ValidationError('Miejsce można potwierdzić po kwalifikacji i przed końcem tury.')
        app.status = 'confirmed'
    elif action == 'withdraw':
        if app.status == 'withdrawn':
            return app
        if app.status in ['canceled', 'expired'] or app.offer.campaign.closed:
            raise ValidationError('Ta rekrutacja jest już zakończona.')
        app.status = 'withdrawn'
    elif action == 'continue':
        round_ = active_round(app.offer)
        check_open(app.offer, round_)
        if app.status not in ['waitlist', 'expired', 'withdrawn', 'rejected'] or round_.number <= app.round.number:
            raise ValidationError('Ponowne zgłoszenie jest dostępne w kolejnej turze.')
        app.round, app.status = round_, 'draft'
        app.payment_approved = False
        app.feedback = ''
    else:
        raise ValidationError('Nieznana czynność.')
    app.revision += 1
    app.save()
    audit(user, f'application.{action}', app.public_id)
    return app


@transaction.atomic
def move_clock(user, campaign_id, target):
    require_staff(user, admin=True)
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    if campaign.demo_clock is None:
        raise ValidationError('Zegar można zmieniać wyłącznie w naborze demonstracyjnym.')
    if target <= campaign.now() or target > campaign.end:
        raise ValidationError('Wybierz późniejszy termin, nie później niż koniec rekrutacji.')
    ending = campaign.rounds.filter(end__gt=campaign.now(), end__lte=target)
    for round_ in ending:
        for offer in campaign.offers.filter(degree=round_.degree):
            has_apps = offer.applications.filter(round=round_).exclude(status__in=['draft', 'rejected', 'withdrawn']).exists()
            if has_apps and not offer.publications.filter(round=round_).exists():
                raise ValidationError(f'Najpierw opublikuj listę: {offer.program.name}, {offer.get_mode_display()}, tura {round_.number}.')
            for app in offer.applications.filter(round=round_, status='qualified'):
                app.status = 'expired'
                app.save(update_fields=['status'])
                notify(app.candidate, 'Termin potwierdzenia minął', f'{offer.program.name}: miejsce nie zostało potwierdzone.')
    previous_time = campaign.now()
    campaign.demo_clock = target
    campaign.save(update_fields=['demo_clock'])
    audit(user, 'campaign.clock', campaign.id, target=target.isoformat())
    for round_ in campaign.rounds.filter(degree__in=['I', 'II'], number=2, start__gt=previous_time, start__lte=target):
        for offer in campaign.offers.filter(degree=round_.degree, state='open'):
            confirmed = offer.applications.filter(status='confirmed').count()
            active = offer.applications.filter(round=round_, status__in=['submitted', 'correction', 'verified', 'qualified']).count()
            if confirmed + active < offer.minimum:
                for app in offer.applications.exclude(status__in=['withdrawn', 'rejected', 'canceled', 'draft']):
                    notify(app.candidate, 'Zainteresowanie ofertą poniżej minimum',
                           f'{offer.program.name}: potwierdzone miejsca i aktywne zgłoszenia są poniżej minimum {offer.minimum}. Nabór wciąż trwa.')
    if target == campaign.end:
        finalize(user, campaign.id)
    return campaign


@transaction.atomic
def finalize(user, campaign_id):
    require_staff(user)
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    if campaign.closed:
        return campaign
    if campaign.now() < campaign.end:
        raise ValidationError('Uruchomienie kierunków rozstrzyga się po zakończeniu ostatnich tur.')
    if Application.objects.filter(offer__campaign=campaign, status__in=['submitted', 'correction', 'verified']).exists():
        raise ValidationError('Przed zamknięciem naboru rozpatrz zgłoszenia i opublikuj wymagane listy.')
    Application.objects.filter(offer__campaign=campaign, status='qualified').update(status='expired')
    for offer in campaign.offers.select_for_update().select_related('program__faculty'):
        count = offer.applications.filter(status='confirmed').values('candidate_id').distinct().count()
        offer.state = 'launched' if count >= offer.minimum else 'canceled'
        offer.save(update_fields=['state'])
        applications = offer.applications.exclude(status__in=['withdrawn', 'rejected', 'draft'])
        if offer.state == 'canceled':
            applications.update(status='canceled')
        text = f'{offer.program.name}: {offer.get_state_display()}. Potwierdzone miejsca: {count}.'
        record_notifications([Notification(user_id=user_id, title='Zakończenie rekrutacji', message=text)
                              for user_id in applications.values_list('candidate_id', flat=True)])
        if offer.state == 'launched' and offer.degree in ['I','II']:
            schedule = DEPARTMENT_PLANS.get(offer.program.faculty.code,SCHEDULES)
            text = (f'Gratulacje! Uruchomiono kierunek {offer.program.name}. '
                    f'{WELCOME_OATH_INSTRUCTION} '
                    f'Plan zajęć i informacje dla studentów: {schedule} '
                    f'Aktywacja uczelnianego konta Teams i Outlook: {ACCOUNTS} Delta: {DELTA} Adapciak: {ADAPCIAK}')
            record_notifications([
                Notification(user_id=id_, title=WELCOME_NOTIFICATION, message=text)
                for id_ in applications.filter(status='confirmed').values_list('candidate_id',flat=True)
            ])
        audit(user, 'offer.finalized', offer.id, state=offer.state, confirmed=count)
    from .housing import allocate_dorms
    allocate_dorms(campaign,user)
    campaign.closed = True
    campaign.save(update_fields=['closed'])
    return campaign


@transaction.atomic
def approve_photo(user, app_id, approved, expected_revision=None, expected_photo_id=None):
    app = locked_application(app_id, user, staff=True)
    check_review_revision(app, expected_revision)
    if app.sworn_at:
        raise ValidationError('Zdjęcie użyte po ślubowaniu jest już zamrożone.')
    if app.status == 'draft':
        raise ValidationError('Zdjęcie można ocenić po złożeniu zgłoszenia.')
    photo = current_photo(app.candidate_id)
    if not photo:
        raise ValidationError('Kandydat nie dodał zdjęcia w profilu.')
    if expected_photo_id is not None:
        check_photo_version(photo, {'expected_photo_id': expected_photo_id})
    if not approved:
        raise ValidationError('Kandydat może podmienić zdjęcie w profilu, jeśli wymaga poprawy.')
    return accept_photo(photo, user)


def oath_problem(app, photo, has_pesel):
    if not app.offer.campaign.closed or app.offer.state != 'launched' or app.status != 'confirmed':
        return 'Ślubowanie jest dostępne po końcu wszystkich tur, dla potwierdzonego miejsca na uruchomionym kierunku.'
    if not has_pesel:
        return 'Zapisz PESEL w zakładce „Mój profil”, aby złożyć ślubowanie.'
    if not photo or not photo.approved_at:
        return 'Ślubowanie będzie dostępne po akceptacji zdjęcia z profilu.'
    return ''


@transaction.atomic
def take_oath(user, app_id, accepted):
    app = locked_application(app_id, user)
    if app.sworn_at:
        return app
    if not accepted:
        raise ValidationError('Potwierdź złożenie ślubowania.')
    photo = current_photo(app.candidate_id)
    problem = oath_problem(app, photo, CandidateIdentity.objects.filter(user_id=app.candidate_id).exists())
    if problem:
        raise ValidationError(problem)
    app.oath_photo = photo
    app.sworn_at = timezone.now()
    app.student_number = f'PK-DEMO-{app.offer.campaign.start.year}-{app.id:06}'
    app.save(update_fields=['sworn_at', 'student_number', 'oath_photo'])
    audit(user, 'enrollment.oath', app.public_id, text=OATH_TEXT, student_number=app.student_number)
    notify(user, 'Witaj w społeczności akademickiej!', f'{app.offer.program.name}: ślubowanie zapisane. Twój podgląd legitymacji jest już dostępny.')
    return app


@transaction.atomic
def ranking_preview(user, offer_id):
    require_staff(user)
    offer = locked_offer(offer_id)
    round_ = active_round(offer) or offer.campaign.rounds.filter(degree=offer.degree).order_by('-number').first()
    earlier = offer.applications.filter(status='confirmed').exclude(round=round_).count()
    available = max(0, offer.capacity - earlier)
    apps = list(offer.applications.filter(round=round_, status__in=['verified', 'qualified', 'waitlist', 'confirmed']).select_related('candidate'))
    rows = []
    for app in apps:
        app.offer = offer
        rows.append((app.id, calculate(app), app.submitted_at))
    ordered, selected = select_with_ties(rows, available, offer.degree)
    by_id = {a.id: a for a in apps}
    pending = offer.applications.filter(round=round_, status__in=['submitted', 'correction']).count()
    latest = offer.publications.filter(round=round_).order_by('-version').first()
    result, rank, last_score = [], 0, object()
    for index, (ident, score, submitted) in enumerate(ordered, 1):
        if offer.degree == 'PG' or last_score != score.score:
            rank = index
        last_score = score.score
        app = by_id[ident]
        result.append({'id': ident, 'rank': rank, 'candidate': f'{app.candidate.first_name} {app.candidate.last_name}',
                       'score': str(score.score) if score.score is not None else None, 'selected': ident in selected,
                       'status': app.status, 'status_label': app.get_status_display(), 'submitted_at': submitted})
    return {'rows': result, 'round': round_.number, 'available': available, 'pending': pending,
            'qualified': len(selected), 'overflow': max(0, len(selected) - available),
            'published_version': latest.version if latest else None,
            'publication_ready': bool(not latest and not pending and apps and offer.state == 'open'
                                      and round_.application_end <= offer.campaign.now() < round_.end)}


def batch_operation(user, operation, identifiers, data, preview=False):
    require_staff(user)
    if operation not in ['verify', 'publish', 'confirm_demo']:
        raise ValidationError('Nieznana operacja zbiorcza.')
    if operation == 'confirm_demo':
        require_staff(user, admin=True)
    if not isinstance(identifiers, list) or not identifiers or len(identifiers) > 250 or any(type(i) is not int or not 0 < i < 2**63 for i in identifiers):
        raise ValidationError('Wybierz od 1 do 250 pozycji.')
    results = []
    with transaction.atomic():
        for ident in sorted(set(identifiers)):
            subject = 'Zgłoszenie niedostępne' if operation != 'publish' else 'Oferta niedostępna'
            try:
                with transaction.atomic():
                    if operation == 'publish':
                        offer = Offer.objects.select_related('program').get(pk=ident)
                        subject = f'{offer.program.name} · {offer.get_degree_display()} · {offer.get_mode_display()}'
                        expected_round = data.get('expected_rounds', {}).get(str(ident))
                        publication = publish(user, ident, expected_round=expected_round, reject_existing=True)
                        message = f'{publication.qualified_count} zakwalifikowanych, wersja {publication.version}'
                    else:
                        app = locked_application(ident, user, staff=True)
                        subject = f'{app.candidate.get_full_name()} · {app.offer.program.name} · {app.offer.get_mode_display()}'
                        if operation == 'verify':
                            if app.status != 'submitted':
                                raise ValidationError('Operacja dotyczy wyłącznie zgłoszeń oczekujących na weryfikację.')
                            if app.bonus_claimed:
                                raise ValidationError('Premię za osiągnięcie należy najpierw ocenić indywidualnie.')
                            expected_revision = data.get('expected_revisions', {}).get(str(ident))
                            grade = 'accepted' if app.offer.portfolio_required and data.get('portfolio_grade') == 'accepted' else 'none'
                            options = dict(data, decision='verify', bonus_category='', expected_revision=expected_revision, portfolio_grade=grade)
                            if str(ident) in data.get('expected_photos', {}):
                                options['expected_photo_id'] = data['expected_photos'][str(ident)]
                            review(user, ident, options)
                            message = 'Dokumenty, zdjęcie i opłata zatwierdzone'
                        else:
                            if not app.candidate.is_demo or app.offer.campaign.demo_clock is None:
                                raise ValidationError('Zbiorcze potwierdzenie jest dostępne tylko dla kont demonstracyjnych.')
                            candidate_decision(app.candidate, ident, 'confirm')
                            audit(user, 'demo.place_confirmed', app.public_id)
                            message = 'Potwierdzono miejsce konta demonstracyjnego'
                    results.append({'id': ident, 'subject': subject, 'ok': True, 'message': message})
            except (ValidationError, RuleError, ObjectDoesNotExist) as error:
                detail = getattr(error, 'detail', str(error))
                if isinstance(error, ObjectDoesNotExist):
                    detail = 'Pozycja jest już niedostępna. Odśwież listę.'
                results.append({'id': ident, 'subject': subject, 'ok': False, 'message': ' '.join(map(str, detail)) if isinstance(detail, list) else str(detail)})
        if preview:
            transaction.set_rollback(True)
    return {'preview': preview, 'results': results, 'success': sum(r['ok'] for r in results)}


@transaction.atomic
def restart_campaign(user, campaign_id):
    require_staff(user, admin=True)
    source = Campaign.objects.select_for_update().get(pk=campaign_id)
    latest = current_campaign()
    if latest.id != source.id:
        return latest  # Retry of the same restart request must not clone twice.
    if not source.closed:
        raise ValidationError('Nową edycję można rozpocząć po zakończeniu obecnej rekrutacji.')
    from datetime import timedelta
    from .models import AllowedSubject, AllowedProfession
    start = source.start.replace(year=source.start.year + 1)
    shift = start - source.start
    campaign = Campaign.objects.create(name=f'Rekrutacja {start.year}/{start.year+1}',
        start=start, end=source.end + shift, demo_clock=start)
    for r in source.rounds.all():
        Round.objects.create(campaign=campaign, degree=r.degree, number=r.number,
            start=r.start + shift, application_end=r.application_end + shift, end=r.end + shift)
    for o in source.offers.all():
        new = Offer.objects.create(campaign=campaign, program=o.program, degree=o.degree, mode=o.mode,
            capacity=o.capacity, minimum=o.minimum, fee=o.fee, portfolio_required=o.portfolio_required,
            portfolio_bonus=o.portfolio_bonus, photo_required=True, rule_version='2027.2',
            tuition_per_semester=o.tuition_per_semester)
        AllowedSubject.objects.bulk_create([AllowedSubject(offer=new, subject=s.subject) for s in o.allowed_subjects.all()])
        AllowedProfession.objects.bulk_create([AllowedProfession(offer=new, name=p.name) for p in o.allowed_professions.all()])
    audit(user, 'campaign.restarted', campaign.id, previous=source.id)
    return campaign
