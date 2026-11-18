from django.db import migrations
from django.db.models import Q


def legacy(apps, schema_editor):
    Application = apps.get_model('admissions', 'Application')
    User = apps.get_model('admissions', 'User')
    Application.objects.filter(bonus_approved=True).update(bonus_points=50, bonus_category='legacy50')
    User.objects.filter(Q(email__in=['kandydat@demo.local', 'komisja@demo.local', 'admin@demo.local']) |
                        Q(email__regex=r'^synthetic[0-9]{3}@demo\.local$')).update(is_demo=True)


SQL = r'''
CREATE OR REPLACE FUNCTION pk_wr(m numeric, p1 numeric, p2 numeric, bonus numeric)
RETURNS numeric LANGUAGE plpgsql IMMUTABLE STRICT AS $$
BEGIN
  IF NOT (m BETWEEN 0 AND 100 AND p1 BETWEEN 0 AND 100 AND p2 BETWEEN 0 AND 100
          AND bonus BETWEEN 0 AND 50 AND bonus = trunc(bonus)) THEN
    RAISE EXCEPTION 'Invalid WR components';
  END IF;
  RETURN LEAST(1000::numeric, 2*m + 6*p1 + 2*p2 + bonus);
END $$;

CREATE FUNCTION pk_oath_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.sworn_at IS NOT NULL AND
    (NEW.sworn_at IS DISTINCT FROM OLD.sworn_at OR NEW.student_number IS DISTINCT FROM OLD.student_number
     OR NOT NEW.photo_approved) THEN
    RAISE EXCEPTION 'An accepted oath and its identity evidence are immutable';
  END IF;
  IF NEW.sworn_at IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM admissions_offer o JOIN admissions_campaign c ON c.id=o.campaign_id
      WHERE o.id=NEW.offer_id AND c.closed AND o.state='launched' AND NEW.status='confirmed'
        AND NEW.photo_approved AND NEW.student_number IS NOT NULL
        AND EXISTS (SELECT 1 FROM admissions_document d WHERE d.application_id=NEW.id AND d.kind='photo')) THEN
    RAISE EXCEPTION 'Oath requires closed admission, launched offer, confirmed place and approved photo';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER oath_guard BEFORE INSERT OR UPDATE ON admissions_application
FOR EACH ROW EXECUTE FUNCTION pk_oath_guard();

CREATE FUNCTION pk_photo_freeze() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.kind='photo' AND EXISTS (SELECT 1 FROM admissions_application WHERE id=NEW.application_id AND sworn_at IS NOT NULL) THEN
    RAISE EXCEPTION 'Photo is frozen after the oath';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER photo_freeze BEFORE INSERT OR UPDATE ON admissions_document
FOR EACH ROW EXECUTE FUNCTION pk_photo_freeze();
'''


class Migration(migrations.Migration):
    dependencies = [('admissions', '0004_application_bonus_category_application_bonus_points_and_more')]
    operations = [migrations.RunPython(legacy, migrations.RunPython.noop), migrations.RunSQL(SQL)]
