from datetime import datetime, timedelta, timezone as tz
from django.core.management.base import BaseCommand
from django.db import transaction
from admissions.models import *
from admissions import catalog_data as c
from admissions.demo import prepare_samples, populate_campaign
from admissions.tuition import demo_tuition


class Command(BaseCommand):
    help = 'Idempotently create a separate, fictitious demonstration campaign.'

    def add_arguments(self, parser):
        parser.add_argument('--password', required=True)

    @transaction.atomic
    def handle(self, *args, **opts):
        prepare_samples()
        if Campaign.objects.exists():
            return
        start = datetime(2027, 6, 1, 8, tzinfo=tz.utc)
        campaign = Campaign.objects.create(name='Rekrutacja 2027/2028', start=start,
                                            end=start + timedelta(days=60), demo_clock=start + timedelta(days=3))
        for degree, count, length in [('I', 3, 20), ('II', 2, 30), ('PG', 2, 30)]:
            for i in range(count):
                end = start + timedelta(days=length * (i + 1))
                Round.objects.create(campaign=campaign, degree=degree, number=i + 1,
                                     start=start + timedelta(days=length * i), application_end=end - timedelta(days=5), end=end)
        faculties = {}
        for code, name, color in c.FACULTIES:
            faculties[code] = Faculty.objects.create(code=code, name=name, color=color)
        def offer(program, degree, mode):
            o = Offer.objects.create(campaign=campaign, program=program, degree=degree, mode=mode,
                capacity={'I': 30, 'II': 20, 'PG': 15}[degree], minimum=20 if degree == 'I' else 10,
                fee=85, photo_required=True, rule_version='2027.2', portfolio_required=program.name == 'Architektura',
                tuition_per_semester=demo_tuition(program.faculty.code, degree, mode),
                portfolio_bonus=degree == 'I' and (program.faculty.code == 'WA' or 'Informatyka' in program.name))
            if degree == 'I':
                AllowedSubject.objects.bulk_create([AllowedSubject(offer=o, subject=s) for s in c.SUBJECTS[program.faculty.code]])
                AllowedProfession.objects.bulk_create([AllowedProfession(offer=o, name=s) for s in c.PROFESSIONS.get(program.name, [])])
            return o
        for code, programs in c.PROGRAMS.items():
            for name, bachelor, master, description in programs:
                program = Program.objects.create(name=name, faculty=faculties[code], description=description, source=c.DEGREES_SOURCE)
                for degree, modes in [('I', bachelor), ('II', master)]:
                    for mode in modes:
                        offer(program, degree, mode)
            program = Program.objects.create(name=c.POSTGRADUATE[code], faculty=faculties[code],
                        description='Rozwijaj specjalistyczne kompetencje. W demonstracyjnym naborze decyduje kolejność kompletnych zgłoszeń; wymagany jest dyplom co najmniej I stopnia.',
                        source='' if code == 'WIiM' else c.PG_SOURCE, illustrative=code == 'WIiM')
            offer(program, 'PG', 'N')
        joint = Program.objects.create(name='Gospodarka przestrzenna', faculty=faculties['WA'],
                    description='Łącz urbanistykę, infrastrukturę i środowisko. Kierunek międzywydziałowy WA, WILiT i WIŚiE.', source=c.DEGREES_SOURCE)
        joint.partner_faculties.add(faculties['WILiT'], faculties['WIŚiE'])
        offer(joint, 'I', 'S')
        accounts = {}
        for role, first, last in [('candidate', 'Anna', 'Kowalska'), ('commission', 'Maria', 'Nowak'), ('admin', 'Piotr', 'Administrator')]:
            email = {'candidate': 'kandydat@demo.local', 'commission': 'komisja@demo.local', 'admin': 'admin@demo.local'}[role]
            accounts[role] = User.objects.create_user(username=email, email=email, password=opts['password'], role=role, first_name=first, last_name=last, is_demo=True)
        anna = accounts['candidate']
        for subject, level, value in [('matematyka', 'basic', 90), ('informatyka', 'extended', 88), ('fizyka', 'extended', 74)]:
            ExamResult.objects.create(user=anna, subject=subject, level=level, value=value)
        AcademicAverage.objects.create(user=anna, value='4.65')
        Diploma.objects.create(user=anna, title='inżynier')
        Notification.objects.create(user=anna, title='Twój kolejny krok', message='Wybierz kierunek i utwórz zgłoszenie. Profil zawiera przykładowe wyniki; dokumenty demonstracyjne znajdziesz obok programu w folderze demo-dokumenty.')
        populate_campaign(campaign, accounts['admin'])
