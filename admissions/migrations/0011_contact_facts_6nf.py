"""Lossless contact decomposition, retaining the application's SQL/ORM interface."""
import django.db.models.deletion
from django.db import migrations, models

VIEW = """
CREATE VIEW admissions_candidatecontact AS
SELECT a.user_id,
 coalesce((SELECT value FROM admissions_candidatephone WHERE user_id=a.user_id), ''::varchar)::varchar(30) AS phone,
 coalesce((SELECT value FROM admissions_candidateportfolio WHERE user_id=a.user_id), ''::varchar)::varchar(500) AS portfolio_url,
 coalesce((SELECT value FROM admissions_candidatenotificationaddress WHERE user_id=a.user_id), ''::varchar)::varchar(254) AS notification_email
FROM admissions_contactanchor a;

CREATE FUNCTION pk_contact_write() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
BEGIN
 IF TG_OP='DELETE' THEN
   DELETE FROM admissions_candidatephone WHERE user_id=OLD.user_id;
   DELETE FROM admissions_candidateportfolio WHERE user_id=OLD.user_id;
   DELETE FROM admissions_candidatenotificationaddress WHERE user_id=OLD.user_id;
   DELETE FROM admissions_contactanchor WHERE user_id=OLD.user_id;
   RETURN OLD;
 END IF;
 IF TG_OP='INSERT' THEN
   INSERT INTO admissions_contactanchor(user_id) VALUES(NEW.user_id);
 ELSE
   IF NEW.user_id IS DISTINCT FROM OLD.user_id THEN
     RAISE EXCEPTION 'The contact owner cannot be changed' USING ERRCODE='23514';
   END IF;
   PERFORM 1 FROM admissions_contactanchor WHERE user_id=OLD.user_id FOR UPDATE;
 END IF;
 IF TG_OP='INSERT' OR NEW.phone IS DISTINCT FROM OLD.phone THEN
 IF NEW.phone = '' THEN
   DELETE FROM admissions_candidatephone WHERE user_id=NEW.user_id;
 ELSE
   INSERT INTO admissions_candidatephone(user_id,value) VALUES(NEW.user_id,NEW.phone)
   ON CONFLICT(user_id) DO UPDATE SET value=EXCLUDED.value;
 END IF;
 END IF;
 IF TG_OP='INSERT' OR NEW.portfolio_url IS DISTINCT FROM OLD.portfolio_url THEN
 IF NEW.portfolio_url = '' THEN
   DELETE FROM admissions_candidateportfolio WHERE user_id=NEW.user_id;
 ELSE
   INSERT INTO admissions_candidateportfolio(user_id,value) VALUES(NEW.user_id,NEW.portfolio_url)
   ON CONFLICT(user_id) DO UPDATE SET value=EXCLUDED.value;
 END IF;
 END IF;
 IF TG_OP='INSERT' OR NEW.notification_email IS DISTINCT FROM OLD.notification_email THEN
 IF NEW.notification_email = '' THEN
   DELETE FROM admissions_candidatenotificationaddress WHERE user_id=NEW.user_id;
 ELSE
   INSERT INTO admissions_candidatenotificationaddress(user_id,value) VALUES(NEW.user_id,NEW.notification_email)
   ON CONFLICT(user_id) DO UPDATE SET value=EXCLUDED.value;
 END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION pk_contact_write() FROM PUBLIC;
CREATE TRIGGER contact_write INSTEAD OF INSERT OR UPDATE OR DELETE
ON admissions_candidatecontact FOR EACH ROW EXECUTE FUNCTION pk_contact_write();
"""


def split_contact(apps, editor):
    with editor.connection.cursor() as cursor:
        cursor.execute("""
          INSERT INTO admissions_contactanchor(user_id) SELECT user_id FROM admissions_candidatecontact;
          INSERT INTO admissions_candidatephone(user_id,value)
            SELECT user_id,phone FROM admissions_candidatecontact WHERE phone<>'';
          INSERT INTO admissions_candidateportfolio(user_id,value)
            SELECT user_id,portfolio_url FROM admissions_candidatecontact WHERE portfolio_url<>'';
          INSERT INTO admissions_candidatenotificationaddress(user_id,value)
            SELECT user_id,notification_email FROM admissions_candidatecontact WHERE notification_email<>'';
          CREATE TEMP TABLE contact_before ON COMMIT DROP AS TABLE admissions_candidatecontact;
          DROP TABLE admissions_candidatecontact;
        """)
        cursor.execute(VIEW)
        cursor.execute("""
          SELECT count(*) FROM (
            (TABLE contact_before EXCEPT TABLE admissions_candidatecontact)
            UNION ALL (TABLE admissions_candidatecontact EXCEPT TABLE contact_before)
          ) difference
        """)
        if cursor.fetchone()[0]:
            raise RuntimeError('Contact decomposition was not lossless; migration rolled back.')


def join_contact(apps, editor):
    with editor.connection.cursor() as cursor:
        cursor.execute("""
          CREATE TEMP TABLE contact_before ON COMMIT DROP AS TABLE admissions_candidatecontact;
          DROP VIEW admissions_candidatecontact;
          DROP FUNCTION pk_contact_write();
          CREATE TABLE admissions_candidatecontact (
            user_id bigint PRIMARY KEY REFERENCES admissions_user(id) DEFERRABLE INITIALLY DEFERRED,
            phone varchar(30) NOT NULL, portfolio_url varchar(500) NOT NULL,
            notification_email varchar(254) NOT NULL
          );
          INSERT INTO admissions_candidatecontact SELECT * FROM contact_before;
        """)


class Migration(migrations.Migration):
    dependencies = [('admissions', '0010_notification_email')]

    operations = [
        migrations.CreateModel(
            name='ContactAnchor',
            fields=[('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True, serialize=False, to='admissions.user'))],
        ),
        *[
            migrations.CreateModel(
                name=name,
                fields=[
                    ('contact', models.OneToOneField(db_column='user_id',
                        on_delete=django.db.models.deletion.CASCADE, primary_key=True,
                        serialize=False, to='admissions.contactanchor')),
                    ('value', field),
                ],
                options={'constraints': [models.CheckConstraint(condition=~models.Q(value=''), name=check)]},
            )
            for name, field, check in [
                ('CandidatePhone', models.CharField(max_length=30), 'phone_fact_nonempty'),
                ('CandidatePortfolio', models.URLField(max_length=500), 'portfolio_fact_nonempty'),
                ('CandidateNotificationAddress', models.EmailField(max_length=254), 'notification_fact_nonempty'),
            ]
        ],
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(split_contact, join_contact)],
            state_operations=[migrations.AlterModelOptions(name='candidatecontact', options={'managed': False})],
        ),
    ]
