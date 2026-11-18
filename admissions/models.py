import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        CANDIDATE = 'candidate', 'Kandydat'
        COMMISSION = 'commission', 'Komisja rekrutacyjna'
        ADMIN = 'admin', 'Administrator'
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.CANDIDATE)
    recovery_hash = models.CharField(max_length=128, blank=True)
    totp_secret = models.CharField(max_length=64, blank=True)
    totp_pending = models.CharField(max_length=64, blank=True)
    totp_last_step = models.BigIntegerField(default=0)
    is_demo = models.BooleanField(default=False)


class Session(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()


class CandidateContact(models.Model):
    """Writable compatibility view over the three independent contact facts."""
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    phone = models.CharField(max_length=30, blank=True)
    portfolio_url = models.URLField(max_length=500, blank=True)
    notification_email = models.EmailField(max_length=254, blank=True)

    class Meta:
        managed = False


class ContactAnchor(models.Model):
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)


class CandidatePhone(models.Model):
    contact = models.OneToOneField(ContactAnchor, primary_key=True, on_delete=models.CASCADE, db_column='user_id')
    value = models.CharField(max_length=30)

    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(value=''), name='phone_fact_nonempty')]


class CandidatePortfolio(models.Model):
    contact = models.OneToOneField(ContactAnchor, primary_key=True, on_delete=models.CASCADE, db_column='user_id')
    value = models.URLField(max_length=500)

    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(value=''), name='portfolio_fact_nonempty')]


class CandidateNotificationAddress(models.Model):
    contact = models.OneToOneField(ContactAnchor, primary_key=True, on_delete=models.CASCADE, db_column='user_id')
    value = models.EmailField(max_length=254)

    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(value=''), name='notification_fact_nonempty')]


class CandidateIdentity(models.Model):
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    pesel = models.CharField(max_length=11, unique=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(pesel__regex=r'^[0-9]{11}$'), name='pesel_digits')]


class Residence(models.Model):
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    city = models.CharField(max_length=100)
    street = models.CharField(max_length=150, blank=True)
    building = models.CharField(max_length=20)
    apartment = models.CharField(max_length=20, blank=True)
    postal_code = models.CharField(max_length=6)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(Q(latitude__isnull=True, longitude__isnull=True) |
                       Q(latitude__isnull=False, longitude__isnull=False, latitude__gte=-90, latitude__lte=90,
                         longitude__gte=-180, longitude__lte=180)), name='residence_coordinate_pair')]


def profile_photo_path(instance, filename):
    from pathlib import Path
    return f'profile/{instance.user_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class ProfilePhoto(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='profile_photos')
    version = models.PositiveIntegerField()
    file = models.FileField(upload_to=profile_photo_path)
    original_name = models.CharField(max_length=200)
    sha256 = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+', null=True, blank=True)

    class Meta:
        ordering = ['-version']
        constraints = [models.UniqueConstraint(fields=['user', 'version'], name='profile_photo_version')]


class ProfileDocument(models.Model):
    class Kind(models.TextChoices):
        EDUCATION = 'education', 'Świadectwo maturalne'
        DIPLOMA = 'diploma', 'Dyplom studiów'
        PORTFOLIO = 'portfolio', 'Portfolio'
        BONUS = 'bonus', 'Olimpiada lub inne osiągnięcie'
        QUALIFICATION = 'qualification', 'Dyplom technika'

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='profile_documents')
    kind = models.CharField(max_length=16, choices=Kind.choices)
    version = models.PositiveIntegerField()
    file = models.FileField(upload_to=profile_photo_path)
    original_name = models.CharField(max_length=200)
    sha256 = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['kind', '-version']
        constraints = [models.UniqueConstraint(fields=['user', 'kind', 'version'], name='profile_document_version')]


class AcademicAverage(models.Model):
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    value = models.DecimalField(max_digits=4, decimal_places=2)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(value__gte=2) & Q(value__lte=5), name='average_2_5')]


class Diploma(models.Model):
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    title = models.CharField(max_length=120)


class ExamResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_results')
    subject = models.CharField(max_length=80)
    level = models.CharField(max_length=12, choices=[('basic', 'Podstawowy'), ('extended', 'Rozszerzony'), ('technical', 'Technik')])
    value = models.DecimalField(max_digits=5, decimal_places=2)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'subject', 'level'], name='one_exam_result'),
            models.CheckConstraint(condition=Q(value__gte=0) & Q(value__lte=100), name='exam_0_100'),
        ]


class Faculty(models.Model):
    code = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=150)
    color = models.CharField(max_length=7)


class Program(models.Model):
    name = models.CharField(max_length=200)
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT)
    partner_faculties = models.ManyToManyField(Faculty, related_name='joint_programs', blank=True)
    description = models.TextField()
    source = models.URLField(max_length=500, blank=True)
    illustrative = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['name', 'faculty'], name='program_faculty_name')]


class Campaign(models.Model):
    name = models.CharField(max_length=100)
    start = models.DateTimeField()
    end = models.DateTimeField()
    demo_clock = models.DateTimeField(null=True, blank=True)
    closed = models.BooleanField(default=False)
    demo_scenario = models.CharField(max_length=40, blank=True)
    def now(self):
        return self.demo_clock or timezone.now()


class Round(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name='rounds')
    degree = models.CharField(max_length=2, choices=[('I', 'I stopień'), ('II', 'II stopień'), ('PG', 'Podyplomowe')])
    number = models.PositiveSmallIntegerField()
    start = models.DateTimeField()
    application_end = models.DateTimeField()
    end = models.DateTimeField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['campaign', 'degree', 'number'], name='one_round'),
                       models.CheckConstraint(condition=Q(start__lt=models.F('application_end')) & Q(application_end__lt=models.F('end')), name='round_dates')]
        ordering = ['degree', 'number']


class Offer(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name='offers')
    program = models.ForeignKey(Program, on_delete=models.PROTECT)
    degree = models.CharField(max_length=2, choices=Round._meta.get_field('degree').choices)
    mode = models.CharField(max_length=2, choices=[('S', 'Stacjonarne'), ('N', 'Niestacjonarne')])
    capacity = models.PositiveIntegerField()
    minimum = models.PositiveIntegerField()
    fee = models.DecimalField(max_digits=8, decimal_places=2, default=85)
    tuition_per_semester = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    portfolio_required = models.BooleanField(default=False)
    portfolio_bonus = models.BooleanField(default=False)
    photo_required = models.BooleanField(default=False)
    state = models.CharField(max_length=12, default='open', choices=[('open', 'Nabór'), ('launched', 'Uruchomiono'), ('canceled', 'Nie uruchomiono')])
    rule_version = models.CharField(max_length=30, default='2027.1')
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['campaign', 'program', 'degree', 'mode'], name='unique_offer'),
            models.CheckConstraint(condition=Q(capacity__gte=models.F('minimum')) & Q(minimum__gt=0) & Q(fee__gt=0), name='offer_limits'),
            models.CheckConstraint(condition=~Q(degree='PG') | Q(mode='N'), name='postgraduate_part_time'),
            models.CheckConstraint(condition=Q(tuition_per_semester__isnull=True) | Q(tuition_per_semester__gt=0), name='positive_semester_tuition'),
        ]


class AllowedSubject(models.Model):
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='allowed_subjects')
    subject = models.CharField(max_length=80)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['offer', 'subject'], name='allowed_subject_unique')]


class AllowedProfession(models.Model):
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='allowed_professions')
    name = models.CharField(max_length=80)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['offer', 'name'], name='profession_unique')]


class Application(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Szkic'
        SUBMITTED = 'submitted', 'Do weryfikacji'
        CORRECTION = 'correction', 'Do uzupełnienia'
        VERIFIED = 'verified', 'Dokumenty zatwierdzone'
        REJECTED = 'rejected', 'Odrzucone'
        QUALIFIED = 'qualified', 'Oczekuje na potwierdzenie miejsca'
        WAITLIST = 'waitlist', 'Lista rezerwowa'
        CONFIRMED = 'confirmed', 'Potwierdzono miejsce'
        WITHDRAWN = 'withdrawn', 'Wycofano'
        EXPIRED = 'expired', 'Brak potwierdzenia — termin minął'
        CANCELED = 'canceled', 'Kierunek nieuruchomiony'
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    candidate = models.ForeignKey(User, on_delete=models.PROTECT, related_name='applications')
    offer = models.ForeignKey(Offer, on_delete=models.PROTECT, related_name='applications')
    round = models.ForeignKey(Round, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True)
    revision = models.PositiveIntegerField(default=1)
    input_snapshot = models.JSONField(default=dict)
    feedback = models.TextField(blank=True)
    bonus_claimed = models.BooleanField(default=False)
    bonus_approved = models.BooleanField(default=False)
    bonus_points = models.PositiveSmallIntegerField(default=0)
    bonus_category = models.CharField(max_length=40, blank=True)
    oath_photo = models.ForeignKey(ProfilePhoto, on_delete=models.PROTECT, related_name='student_cards', null=True, blank=True)
    sworn_at = models.DateTimeField(null=True, blank=True)
    student_number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    portfolio_grade = models.CharField(max_length=12, default='none', choices=[('none', 'Nie oceniono'), ('accepted', 'Przyjęte'), ('excellent', 'Wyróżniające'), ('rejected', 'Odrzucone')])
    payment_approved = models.BooleanField(default=False)
    payment_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    portfolio_url = models.URLField(max_length=500, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+', null=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['candidate', 'offer'], name='one_application_per_offer'),
                       models.CheckConstraint(condition=Q(bonus_points__lte=50), name='bonus_0_50')]
        indexes = [models.Index(fields=['offer', 'status', 'submitted_at'], name='application_queue'),
                   models.Index(fields=['candidate', '-created_at'], name='candidate_applications')]


def document_path(instance, filename):
    return f'{instance.application.public_id}/{uuid.uuid4().hex}{__import__("pathlib").Path(filename).suffix.lower()}'


class Document(models.Model):
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name='documents')
    kind = models.CharField(max_length=16, choices=[('education', 'Świadectwo / dyplom'), ('fee', 'Potwierdzenie przelewu'), ('photo', 'Zdjęcie kandydata'), ('portfolio', 'Portfolio'), ('bonus', 'Osiągnięcie'), ('qualification', 'Dyplom technika')])
    reused_from = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='copies')
    profile_source = models.ForeignKey(ProfileDocument, on_delete=models.PROTECT, null=True, blank=True)
    revision = models.PositiveIntegerField()
    file = models.FileField(upload_to=document_path)
    original_name = models.CharField(max_length=200)
    sha256 = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(default=timezone.now)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['application', 'kind', 'revision'], name='document_revision')]


class Publication(models.Model):
    offer = models.ForeignKey(Offer, on_delete=models.PROTECT, related_name='publications')
    round = models.ForeignKey(Round, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(default=timezone.now)
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    reason = models.TextField(blank=True)
    cutoff = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    qualified_count = models.PositiveIntegerField()
    available_places = models.PositiveIntegerField()
    overflow = models.PositiveIntegerField(default=0)
    rule = models.JSONField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['offer', 'round', 'version'], name='publication_version')]


class RankingEntry(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.PROTECT, related_name='entries')
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name='ranking_entries')
    rank = models.PositiveIntegerField()
    score = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    decision = models.CharField(max_length=12)
    explanation = models.JSONField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['publication', 'application'], name='one_ranking_entry')]
        indexes = [models.Index(fields=['publication', 'rank'], name='ranking_order')]


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    read = models.BooleanField(default=False)


class EmailDelivery(models.Model):
    class State(models.TextChoices):
        PENDING = 'pending', 'Oczekuje'
        SENT = 'sent', 'Wysłano'
        CANCELLED = 'cancelled', 'Anulowano'
        FAILED = 'failed', 'Wysyłka nie powiodła się'

    notification = models.OneToOneField(Notification, on_delete=models.CASCADE)
    recipient = models.EmailField(max_length=254)
    state = models.CharField(max_length=10, choices=State.choices, default=State.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=['state', 'available_at'], name='email_delivery_ready_idx')]


class Dormitory(models.Model):
    code = models.CharField(max_length=4, primary_key=True)
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=150)
    description = models.TextField()
    seats = models.PositiveSmallIntegerField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        ordering = ['code']
        constraints = [models.CheckConstraint(condition=Q(seats__gt=0), name='dorm_positive_seats')]


class HousingApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Wniosek złożony'
        AWARDED = 'awarded', 'Miejsce przyznane'
        RESERVE = 'reserve', 'Lista rezerwowa'
        INELIGIBLE = 'ineligible', 'Brak potwierdzonego przyjęcia'
        WITHDRAWN = 'withdrawn', 'Wniosek wycofany'

    candidate = models.ForeignKey(User, on_delete=models.PROTECT)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name='housing_requests')
    preferred = models.ForeignKey(Dormitory, on_delete=models.PROTECT)
    allocated = models.ForeignKey(Dormitory, on_delete=models.PROTECT, related_name='allocations', null=True)
    enrollment = models.ForeignKey(Application, on_delete=models.PROTECT, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    distance_km = models.DecimalField(max_digits=7, decimal_places=2)
    score_index = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    submitted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['candidate', 'campaign'], name='one_housing_request'),
            models.CheckConstraint(condition=Q(distance_km__gte=0), name='housing_distance_positive'),
            models.CheckConstraint(condition=(Q(status='awarded', allocated__isnull=False, enrollment__isnull=False) |
                                              (~Q(status='awarded') & Q(allocated__isnull=True))), name='housing_allocation_status'),
        ]
        indexes = [models.Index(fields=['campaign', 'status', '-distance_km'], name='housing_campaign_distance')]


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    action = models.CharField(max_length=80)
    entity = models.CharField(max_length=120)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        indexes = [models.Index(fields=['-created_at'], name='audit_recent')]


class OfferStats(models.Model):
    """Read model maintained exclusively by the PostgreSQL application trigger."""
    offer = models.OneToOneField(Offer, on_delete=models.CASCADE, primary_key=True, related_name='stats')
    applications = models.BigIntegerField(default=0)
    verified = models.BigIntegerField(default=0)
    confirmed = models.BigIntegerField(default=0)
    class Meta:
        db_table = 'pk_offer_stats'
