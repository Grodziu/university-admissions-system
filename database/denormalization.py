"""Measured 2NF/3NF violation and aggregate projection on isolated TEMP copies.

No permanent application data or planner switches are changed.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import platform
import statistics
import psycopg
from portable import DATA

SETUP = """
CREATE TEMP TABLE dn_faculty AS SELECT id,name FROM admissions_faculty;
ALTER TABLE dn_faculty ADD PRIMARY KEY(id);
CREATE TEMP TABLE dn_program AS SELECT id,name,faculty_id FROM admissions_program;
ALTER TABLE dn_program ADD PRIMARY KEY(id);
CREATE TEMP TABLE dn_offer AS SELECT id,program_id FROM admissions_offer;
ALTER TABLE dn_offer ADD PRIMARY KEY(id);
CREATE TEMP TABLE dn_subject AS SELECT offer_id,subject FROM admissions_allowedsubject;
ALTER TABLE dn_subject ADD PRIMARY KEY(offer_id,subject);
CREATE TEMP TABLE dn_application (id bigint PRIMARY KEY,offer_id bigint NOT NULL,status text NOT NULL);
INSERT INTO dn_application
SELECT n, ids[1+((n-1) %% cardinality(ids))::int],
 CASE WHEN n %% 7=0 THEN 'confirmed' WHEN n %% 3=0 THEN 'verified' ELSE 'submitted' END
FROM generate_series(1,%(rows)s) n
CROSS JOIN (SELECT array_agg(id ORDER BY id) ids FROM dn_offer) offers;
CREATE TEMP TABLE dn_plain (LIKE dn_application INCLUDING ALL);
INSERT INTO dn_plain TABLE dn_application;

CREATE TEMP TABLE dn_stats(offer_id bigint PRIMARY KEY,applications bigint NOT NULL,verified bigint NOT NULL,confirmed bigint NOT NULL);
INSERT INTO dn_stats
SELECT o.id,count(a.id),count(*) FILTER(WHERE status='verified'),count(*) FILTER(WHERE status='confirmed')
FROM dn_offer o LEFT JOIN dn_application a ON a.offer_id=o.id GROUP BY o.id;

CREATE TEMP TABLE dn_catalog (
 offer_id bigint,subject varchar(80),program_id bigint,program_name varchar(200),
 faculty_id bigint,faculty_name varchar(150),PRIMARY KEY(offer_id,subject)
);
CREATE FUNCTION pg_temp.dn_catalog_refresh() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 DELETE FROM dn_catalog;
 INSERT INTO dn_catalog
 SELECT s.offer_id,s.subject,p.id,p.name,f.id,f.name
 FROM dn_subject s JOIN dn_offer o ON o.id=s.offer_id
 JOIN dn_program p ON p.id=o.program_id JOIN dn_faculty f ON f.id=p.faculty_id;
 RETURN NULL;
END $$;
CREATE TRIGGER dn_refresh_subject AFTER INSERT OR UPDATE OR DELETE ON dn_subject
 FOR EACH STATEMENT EXECUTE FUNCTION pg_temp.dn_catalog_refresh();
CREATE TRIGGER dn_refresh_offer AFTER INSERT OR UPDATE OR DELETE ON dn_offer
 FOR EACH STATEMENT EXECUTE FUNCTION pg_temp.dn_catalog_refresh();
CREATE TRIGGER dn_refresh_program AFTER INSERT OR UPDATE OR DELETE ON dn_program
 FOR EACH STATEMENT EXECUTE FUNCTION pg_temp.dn_catalog_refresh();
CREATE TRIGGER dn_refresh_faculty AFTER INSERT OR UPDATE OR DELETE ON dn_faculty
 FOR EACH STATEMENT EXECUTE FUNCTION pg_temp.dn_catalog_refresh();
UPDATE dn_subject SET subject=subject;

CREATE FUNCTION pg_temp.dn_stats_write() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP IN ('UPDATE','DELETE') THEN
   UPDATE dn_stats SET applications=applications-1,
    verified=verified-(OLD.status='verified')::int,confirmed=confirmed-(OLD.status='confirmed')::int
   WHERE offer_id=OLD.offer_id;
 END IF;
 IF TG_OP IN ('INSERT','UPDATE') THEN
   INSERT INTO dn_stats VALUES(NEW.offer_id,1,(NEW.status='verified')::int,(NEW.status='confirmed')::int)
   ON CONFLICT(offer_id) DO UPDATE SET applications=dn_stats.applications+1,
     verified=dn_stats.verified+EXCLUDED.verified,confirmed=dn_stats.confirmed+EXCLUDED.confirmed;
 END IF;
 RETURN NULL;
END $$;
CREATE TRIGGER dn_application_write AFTER INSERT OR UPDATE OR DELETE ON dn_application
 FOR EACH ROW EXECUTE FUNCTION pg_temp.dn_stats_write();
ANALYZE dn_application; ANALYZE dn_catalog; ANALYZE dn_stats;
"""

NORMALIZED = """
SELECT s.offer_id,s.subject,p.id AS program_id,p.name AS program_name,
 f.id AS faculty_id,f.name AS faculty_name,
 coalesce(t.applications,0) AS applications,coalesce(t.verified,0) AS verified,coalesce(t.confirmed,0) AS confirmed
FROM dn_subject s JOIN dn_offer o ON o.id=s.offer_id
JOIN dn_program p ON p.id=o.program_id JOIN dn_faculty f ON f.id=p.faculty_id
LEFT JOIN (
 SELECT offer_id,count(*) AS applications,count(*) FILTER(WHERE status='verified') AS verified,
 count(*) FILTER(WHERE status='confirmed') AS confirmed
 FROM dn_application GROUP BY offer_id
) t ON t.offer_id=o.id
ORDER BY s.offer_id,s.subject
"""
DENORMALIZED = """
SELECT c.offer_id,c.subject,c.program_id,c.program_name,c.faculty_id,c.faculty_name,
 coalesce(t.applications,0) AS applications,coalesce(t.verified,0) AS verified,coalesce(t.confirmed,0) AS confirmed
FROM dn_catalog c LEFT JOIN dn_stats t ON t.offer_id=c.offer_id
ORDER BY c.offer_id,c.subject
"""


def digest(rows):
    return hashlib.sha256(repr(rows).encode('utf-8')).hexdigest()


def measure(conn, query, repeats):
    conn.execute(query).fetchall()  # warm-up outside the measurements
    plans = [conn.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) ' + query).fetchone()[0][0] for _ in range(repeats)]
    times = [p['Execution Time'] for p in plans]
    return {'median_ms': statistics.median(times), 'runs_ms': times, 'plans': plans,
            'total_cost': statistics.median(p['Plan']['Total Cost'] for p in plans)}


def run(rows=100000, repeats=7, output=None):
    out = Path(output) if output else DATA / 'benchmarks' / ('denormalization-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
    out.mkdir(parents=True, exist_ok=True)
    params = dict(host='127.0.0.1', port=os.environ['PK_DB_PORT'], user=os.environ['PK_DB_USER'],
                  password=os.environ['PK_DB_PASSWORD'], dbname=os.environ['PK_DB_NAME'])
    evidence = {'date_utc': datetime.now(timezone.utc).isoformat(), 'rows': rows, 'repeats': repeats,
        'os': platform.platform(), 'cpu': platform.processor(), 'python': platform.python_version(),
        'scope': 'One connection, TEMP copies of real offer/program/faculty/subject relations, scaled synthetic applications, warm cache.',
        'production_modified': False, 'dml_checks': []}
    with psycopg.connect(**params) as conn:
        evidence['postgresql'] = conn.execute('SELECT version()').fetchone()[0]
        evidence['settings'] = dict(conn.execute("""SELECT name,setting FROM pg_settings WHERE name IN
          ('shared_buffers','work_mem','effective_cache_size','random_page_cost','max_parallel_workers_per_gather')""").fetchall())
        # A setup contains multiple statements; client-side binding preserves safe literals.
        with psycopg.ClientCursor(conn) as setup_cursor:
            setup_cursor.execute(SETUP, {'rows': rows})
        baseline = conn.execute(NORMALIZED).fetchall()
        cached = conn.execute(DENORMALIZED).fetchall()
        if baseline != cached:
            raise AssertionError('Read-model results differ.')
        evidence['result_rows'] = len(baseline)
        evidence['result_sha256'] = digest(baseline)
        for phase, query in [('before', NORMALIZED), ('after', DENORMALIZED)]:
            evidence[phase] = measure(conn, query, repeats)
            (out / (phase + '.sql')).write_text(query.strip()+';\n', encoding='utf-8')
            (out / (phase + '-plans.txt')).write_text('\n'.join(r[0] for r in conn.execute(
                'EXPLAIN (ANALYZE,BUFFERS) ' + query).fetchall()), encoding='utf-8')
        evidence['read_speedup'] = evidence['before']['median_ms'] / evidence['after']['median_ms']
        evidence['estimated_cost_reduction_pct'] = 100*(1-evidence['after']['total_cost']/evidence['before']['total_cost'])
        evidence['projection_bytes'] = conn.execute("SELECT pg_total_relation_size('dn_catalog')+pg_total_relation_size('dn_stats')").fetchone()[0]

        # Every event is checked in both directions (including count multiplicity).
        offer, other = [r[0] for r in conn.execute('SELECT id FROM dn_offer ORDER BY id LIMIT 2')]
        subject = conn.execute('SELECT subject FROM dn_subject WHERE offer_id=%s ORDER BY subject LIMIT 1', [offer]).fetchone()[0]
        operations = [
            ('application INSERT', 'INSERT INTO dn_application VALUES(%s,%s,%s)', [rows+1, offer, 'verified']),
            ('application UPDATE status', "UPDATE dn_application SET status='confirmed' WHERE id=%s", [rows+1]),
            ('application UPDATE offer', 'UPDATE dn_application SET offer_id=%s WHERE id=%s', [other, rows+1]),
            ('application DELETE', 'DELETE FROM dn_application WHERE id=%s', [rows+1]),
            ('subject DELETE', 'DELETE FROM dn_subject WHERE offer_id=%s AND subject=%s', [offer, subject]),
            ('subject INSERT', 'INSERT INTO dn_subject VALUES(%s,%s)', [offer, subject]),
            ('subject UPDATE', 'UPDATE dn_subject SET subject=subject || %s WHERE offer_id=%s AND subject=%s', [' (kontrola)',offer,subject]),
            ('faculty UPDATE', "UPDATE dn_faculty SET name=name || ' (kontrola)' WHERE id=(SELECT min(id) FROM dn_faculty)", []),
            ('program UPDATE', "UPDATE dn_program SET name=name || ' (kontrola)' WHERE id=(SELECT min(id) FROM dn_program)", []),
        ]
        conn.execute('SAVEPOINT checks')
        for label, statement, values in operations:
            conn.execute(statement, values)
            left, right = conn.execute(NORMALIZED).fetchall(), conn.execute(DENORMALIZED).fetchall()
            if left != right:
                raise AssertionError('Broken projection after ' + label)
            evidence['dml_checks'].append({'event': label, 'equal': True, 'rows': len(left), 'sha256': digest(left)})
        conn.execute('ROLLBACK TO SAVEPOINT checks')

        # Same table layout/indexes, same 1000-row DML, rollback each sample.
        evidence['write_1000'] = {}
        for label, template in [
            ('INSERT', "INSERT INTO {table} SELECT id+%(rows)s,offer_id,status FROM dn_plain WHERE id<=1000"),
            ('UPDATE', "UPDATE {table} SET status=CASE WHEN status='confirmed' THEN 'verified' ELSE 'confirmed' END WHERE id<=1000"),
            ('DELETE', "DELETE FROM {table} WHERE id<=1000"),
        ]:
            evidence['write_1000'][label] = {}
            for variant, table in [('without_trigger', 'dn_plain'), ('with_trigger', 'dn_application')]:
                plans = []
                statement = template.format(table=table)
                for trial in range(repeats+1):
                    conn.execute('SAVEPOINT sample')
                    plan = conn.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) ' + statement, {'rows': rows}).fetchone()[0][0]
                    if trial:
                        plans.append(plan)
                    conn.execute('ROLLBACK TO SAVEPOINT sample')
                    conn.execute('RELEASE SAVEPOINT sample')
                times = [p['Execution Time'] for p in plans]
                evidence['write_1000'][label][variant] = {'median_ms': statistics.median(times), 'runs_ms': times, 'plans': plans}
        assert conn.execute(NORMALIZED).fetchall() == conn.execute(DENORMALIZED).fetchall()
        conn.rollback()  # DROP all TEMP objects/functions; canonical relations were only read.
    (out / 'setup.sql').write_text(SETUP.replace('%(rows)s', str(rows)).replace('%%', '%'), encoding='utf-8')
    (out / 'summary.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Pomiar denormalizacji', '', evidence['scope'], '',
        'Klucz kopii katalogu: (offer_id, subject). offer_id -> program_id, program_name, faculty_id, faculty_name: '
        'zależność od części klucza, naruszenie 2NF. program_id -> faculty_id -> faculty_name: '
        'zależności przechodnie, naruszenie 3NF. dn_stats jest osobną projekcją agregatową.', '',
        '| Odczyt | Mediana [ms] | Koszt estymowany |', '|---|---:|---:|',
        f"| Agregacja i JOIN | {evidence['before']['median_ms']:.3f} | {evidence['before']['total_cost']:.2f} |",
        f"| Projekcje | {evidence['after']['median_ms']:.3f} | {evidence['after']['total_cost']:.2f} |", '',
        f"Przyspieszenie mediany: {evidence['read_speedup']:.2f}×. Redukcja kosztu planu: {evidence['estimated_cost_reduction_pct']:.2f}%. "
        f"Wyniki identyczne ({evidence['result_rows']} wierszy, SHA-256 {evidence['result_sha256']}). "
        f"Projekcje wraz z indeksami: {evidence['projection_bytes']} B.", '',
        '| 1000 modyfikacji | Bez triggera [ms] | Z triggerem [ms] |', '|---|---:|---:|---:|']
    for label, cost in evidence['write_1000'].items():
        lines.append(f"| {label} | {cost['without_trigger']['median_ms']:.3f} | {cost['with_trigger']['median_ms']:.3f} |")
    lines += ['', 'Pomiary dotyczą kopii TEMP i jednego połączenia. Wyzwalacze nazw odświeżają mały katalog instrukcyjnie, '
        'a wyzwalacz zgłoszeń aktualizuje liczniki wierszowo. Kontrole po każdej operacji obejmują zmianę statusu i przeniesienie zgłoszenia. '
        'Eksperyment nie zmienia produkcyjnego API ani struktury aplikacji; nie dowodzi, że warto przenieść wszystkie kopie do jej modelu fizycznego.',
        'Koszt planu jest bezjednostkową estymacją optymalizatora. Czas [ms] i narzut utrzymania są osobnymi wynikami.']
    (out / 'wynik.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return str(out)
