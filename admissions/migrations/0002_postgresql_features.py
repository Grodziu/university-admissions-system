from django.db import migrations

SQL = r'''
CREATE FUNCTION pk_wr(m numeric, p1 numeric, p2 numeric, bonus numeric)
RETURNS numeric LANGUAGE plpgsql IMMUTABLE STRICT AS $$
BEGIN
  IF NOT (m BETWEEN 0 AND 100 AND p1 BETWEEN 0 AND 100 AND p2 BETWEEN 0 AND 100 AND bonus IN (0,50)) THEN
    RAISE EXCEPTION 'Invalid WR components';
  END IF;
  RETURN LEAST(1000::numeric, 2*m + 6*p1 + 2*p2 + bonus);
END $$;

CREATE TABLE pk_row_audit (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  transaction_id bigint NOT NULL DEFAULT txid_current(),
  db_actor text NOT NULL DEFAULT session_user,
  operation text NOT NULL,
  application_id bigint NOT NULL,
  before_state jsonb,
  after_state jsonb
);
CREATE TABLE pk_statement_audit (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  operation text NOT NULL,
  affected_rows bigint NOT NULL
);
CREATE TABLE pk_offer_stats (
  offer_id bigint PRIMARY KEY REFERENCES admissions_offer(id),
  applications bigint NOT NULL DEFAULT 0,
  verified bigint NOT NULL DEFAULT 0,
  confirmed bigint NOT NULL DEFAULT 0
);
CREATE FUNCTION pk_application_audit() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE b jsonb; a jsonb;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    b := jsonb_build_object('status',OLD.status,'revision',OLD.revision,'offer',OLD.offer_id,'round',OLD.round_id,'payment_approved',OLD.payment_approved);
    UPDATE pk_offer_stats SET applications=applications-1,
      verified=verified-(CASE WHEN OLD.status IN ('verified','qualified','waitlist','confirmed') THEN 1 ELSE 0 END),
      confirmed=confirmed-(CASE WHEN OLD.status='confirmed' THEN 1 ELSE 0 END) WHERE offer_id=OLD.offer_id;
  END IF;
  IF TG_OP <> 'DELETE' THEN
    a := jsonb_build_object('status',NEW.status,'revision',NEW.revision,'offer',NEW.offer_id,'round',NEW.round_id,'payment_approved',NEW.payment_approved);
    INSERT INTO pk_offer_stats(offer_id,applications,verified,confirmed)
    VALUES(NEW.offer_id,1,CASE WHEN NEW.status IN ('verified','qualified','waitlist','confirmed') THEN 1 ELSE 0 END,CASE WHEN NEW.status='confirmed' THEN 1 ELSE 0 END)
    ON CONFLICT(offer_id) DO UPDATE SET applications=pk_offer_stats.applications+1,
      verified=pk_offer_stats.verified+EXCLUDED.verified, confirmed=pk_offer_stats.confirmed+EXCLUDED.confirmed;
  END IF;
  INSERT INTO pk_row_audit(operation,application_id,before_state,after_state)
    VALUES(TG_OP,COALESCE(NEW.id,OLD.id),b,a);
  RETURN COALESCE(NEW,OLD);
END $$;
CREATE TRIGGER application_row_audit AFTER INSERT OR UPDATE OR DELETE ON admissions_application
FOR EACH ROW EXECUTE FUNCTION pk_application_audit();

CREATE FUNCTION pk_application_statement_audit() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
BEGIN
  INSERT INTO pk_statement_audit(operation,affected_rows) SELECT TG_OP,count(*) FROM changed;
  RETURN NULL;
END $$;
CREATE TRIGGER application_insert_statement AFTER INSERT ON admissions_application
REFERENCING NEW TABLE AS changed FOR EACH STATEMENT EXECUTE FUNCTION pk_application_statement_audit();
CREATE TRIGGER application_update_statement AFTER UPDATE ON admissions_application
REFERENCING NEW TABLE AS changed FOR EACH STATEMENT EXECUTE FUNCTION pk_application_statement_audit();
CREATE TRIGGER application_delete_statement AFTER DELETE ON admissions_application
REFERENCING OLD TABLE AS changed FOR EACH STATEMENT EXECUTE FUNCTION pk_application_statement_audit();

CREATE FUNCTION pk_application_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE o admissions_offer; r admissions_round;
BEGIN
  SELECT * INTO STRICT o FROM admissions_offer WHERE id=NEW.offer_id;
  SELECT * INTO STRICT r FROM admissions_round WHERE id=NEW.round_id;
  IF o.campaign_id<>r.campaign_id OR o.degree<>r.degree THEN
    RAISE EXCEPTION 'Application round must belong to its offer degree and campaign';
  END IF;
  IF NEW.payment_approved AND (NEW.payment_amount IS NULL OR NEW.payment_amount<>o.fee) THEN
    RAISE EXCEPTION 'Approved payment must equal the offer fee';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER application_guard BEFORE INSERT OR UPDATE ON admissions_application
FOR EACH ROW EXECUTE FUNCTION pk_application_guard();

CREATE FUNCTION pk_immutable_publication() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Published admission records are immutable; create a new version'; END $$;
CREATE TRIGGER immutable_publication BEFORE UPDATE OR DELETE ON admissions_publication
FOR EACH ROW EXECUTE FUNCTION pk_immutable_publication();
CREATE TRIGGER immutable_ranking_entry BEFORE UPDATE OR DELETE ON admissions_rankingentry
FOR EACH ROW EXECUTE FUNCTION pk_immutable_publication();

CREATE INDEX application_verified_partial ON admissions_application(offer_id,round_id,submitted_at,id)
WHERE status IN ('verified','qualified','waitlist','confirmed');
CREATE INDEX application_snapshot_gin ON admissions_application USING gin(input_snapshot jsonb_path_ops);
CREATE INDEX audit_time_brin ON pk_row_audit USING brin(occurred_at);
CREATE INDEX program_lower_name ON admissions_program(lower(name));

CREATE VIEW pk_offer_overview AS
SELECT o.id, p.name, f.code AS faculty, o.degree, o.mode, o.capacity, o.minimum,
       COALESCE(s.applications,0) AS applications, COALESCE(s.verified,0) AS verified,
       COALESCE(s.confirmed,0) AS confirmed
FROM admissions_offer o JOIN admissions_program p ON p.id=o.program_id
JOIN admissions_faculty f ON f.id=p.faculty_id LEFT JOIN pk_offer_stats s ON s.offer_id=o.id;

CREATE VIEW pk_candidates_without_confirmed_place AS
SELECT candidate_id FROM admissions_application WHERE status IN ('verified','qualified','waitlist')
EXCEPT SELECT candidate_id FROM admissions_application WHERE status='confirmed';

CREATE PROCEDURE pk_reconcile_offer_stats() LANGUAGE SQL AS $$
  INSERT INTO pk_offer_stats(offer_id,applications,verified,confirmed)
  SELECT o.id,count(a.id), count(a.id) FILTER (WHERE a.status IN ('verified','qualified','waitlist','confirmed')),
         count(a.id) FILTER (WHERE a.status='confirmed')
  FROM admissions_offer o LEFT JOIN admissions_application a ON a.offer_id=o.id GROUP BY o.id
  ON CONFLICT(offer_id) DO UPDATE SET applications=EXCLUDED.applications,verified=EXCLUDED.verified,confirmed=EXCLUDED.confirmed;
$$;
REVOKE ALL ON FUNCTION pk_application_audit(), pk_application_statement_audit() FROM PUBLIC;
'''


class Migration(migrations.Migration):
    dependencies = [('admissions', '0001_initial')]
    operations = [migrations.RunSQL(SQL)]
