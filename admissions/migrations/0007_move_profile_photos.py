from collections import defaultdict

from django.db import migrations
from django.utils import timezone

from admissions.identity import demo_pesel
from admissions.tuition import demo_tuition


def transfer(apps, schema_editor):
    Application = apps.get_model('admissions', 'Application')
    Document = apps.get_model('admissions', 'Document')
    ProfilePhoto = apps.get_model('admissions', 'ProfilePhoto')
    CandidateIdentity = apps.get_model('admissions', 'CandidateIdentity')
    User = apps.get_model('admissions', 'User')
    Offer = apps.get_model('admissions', 'Offer')

    per_user = defaultdict(dict)
    legacy_oaths = {}
    newest_by_app = set()
    documents = (Document.objects.filter(kind='photo').select_related('application')
                 .order_by('-uploaded_at', '-id'))
    for doc in documents.iterator():
        app = doc.application
        newest = app.id not in newest_by_app
        newest_by_app.add(app.id)
        evidence = per_user[app.candidate_id].setdefault(doc.sha256, {
            'file': doc.file.name, 'original_name': doc.original_name, 'uploaded_at': doc.uploaded_at
        })
        if newest and app.photo_approved:
            evidence.setdefault('approved_at', app.sworn_at or timezone.now())
            if app.sworn_at:
                legacy_oaths[app.id] = (app.candidate_id, doc.sha256)

    photos = {}
    for user_id, by_hash in per_user.items():
        for version, digest in enumerate(reversed(by_hash), 1):
            photo = ProfilePhoto.objects.create(user_id=user_id, version=version, sha256=digest, **by_hash[digest])
            photos[(user_id, digest)] = photo.id
    for app_id, key in legacy_oaths.items():
        Application.objects.filter(pk=app_id).update(oath_photo_id=photos[key])

    CandidateIdentity.objects.bulk_create([
        CandidateIdentity(user_id=user_id, pesel=demo_pesel(user_id))
        for user_id in User.objects.filter(is_demo=True, role='candidate').values_list('pk', flat=True)
    ], ignore_conflicts=True)
    for offer in Offer.objects.select_related('campaign', 'program__faculty').iterator():
        if offer.campaign.demo_clock is not None:
            offer.tuition_per_semester = demo_tuition(offer.program.faculty.code, offer.degree, offer.mode)
            offer.save(update_fields=['tuition_per_semester'])


OATH_GUARD = """
CREATE OR REPLACE FUNCTION pk_oath_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.sworn_at IS NOT NULL AND
    (NEW.sworn_at IS DISTINCT FROM OLD.sworn_at OR NEW.student_number IS DISTINCT FROM OLD.student_number
     OR NEW.oath_photo_id IS DISTINCT FROM OLD.oath_photo_id) THEN
    RAISE EXCEPTION 'An accepted oath and its photo are immutable';
  END IF;
  IF NEW.sworn_at IS NOT NULL AND NOT EXISTS (
     SELECT 1 FROM admissions_offer o JOIN admissions_campaign c ON c.id=o.campaign_id
     JOIN admissions_profilephoto p ON p.id=NEW.oath_photo_id
     WHERE o.id=NEW.offer_id AND c.closed AND o.state='launched' AND NEW.status='confirmed'
       AND p.user_id=NEW.candidate_id AND p.approved_at IS NOT NULL AND NEW.student_number IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'Oath requires a confirmed place and the candidate''s approved profile photo';
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION pk_profile_photo_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.user_id, NEW.version, NEW.file, NEW.sha256) IS DISTINCT FROM
     (OLD.user_id, OLD.version, OLD.file, OLD.sha256)
     OR (OLD.approved_at IS NOT NULL AND
         (NEW.approved_at, NEW.approved_by_id) IS DISTINCT FROM (OLD.approved_at, OLD.approved_by_id)) THEN
    RAISE EXCEPTION 'An existing profile photo and its approval cannot be replaced';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER profile_photo_guard BEFORE UPDATE ON admissions_profilephoto
FOR EACH ROW EXECUTE FUNCTION pk_profile_photo_guard();
SET CONSTRAINTS ALL IMMEDIATE;
"""


class Migration(migrations.Migration):
    dependencies = [('admissions', '0006_candidate_profile_and_tuition')]
    operations = [
        migrations.RunPython(transfer),
        migrations.RunSQL(OATH_GUARD),
        migrations.RemoveField(model_name='application', name='photo_approved'),
    ]
