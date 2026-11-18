-- Zapytania odczytowe dla PostgreSQL.
-- Nazwy tabel odpowiadają faktycznym migracjom aplikacji.

-- Q01: skonsolidowany katalog; INNER JOIN + LEFT JOIN z projekcją utrzymywaną przez trigger.
SELECT * FROM pk_offer_overview ORDER BY faculty, degree, mode, name;

-- Q02: kolejka kwalifikacji (indeks częściowy application_verified_partial).
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, submitted_at, input_snapshot
FROM admissions_application
WHERE offer_id = 1 AND round_id = 1
  AND status IN ('verified','qualified','waitlist','confirmed')
ORDER BY submitted_at, id;

-- Q03: połączenie publikacji, rankingu, zgłoszenia oraz programu; GROUP BY / HAVING.
SELECT p.id, pr.name, p.version, p.cutoff, count(e.id) AS liczba_wynikow
FROM admissions_publication p
JOIN admissions_rankingentry e ON e.publication_id=p.id
JOIN admissions_offer o ON o.id=p.offer_id
JOIN admissions_program pr ON pr.id=o.program_id
GROUP BY p.id,pr.name HAVING count(e.id)>0 ORDER BY p.id DESC;

-- Q04: EXCEPT — zainteresowani bez żadnego potwierdzonego miejsca.
SELECT candidate_id FROM admissions_application WHERE status IN ('verified','qualified','waitlist')
EXCEPT
SELECT candidate_id FROM admissions_application WHERE status='confirmed';

-- Q05: INTERSECT — kandydaci ze zgłoszeniem na I stopień i ze zweryfikowaną opłatą.
SELECT a.candidate_id FROM admissions_application a JOIN admissions_offer o ON o.id=a.offer_id WHERE o.degree='I'
INTERSECT
SELECT candidate_id FROM admissions_application WHERE payment_approved;

-- Q06: NOT EXISTS — oferty bez zgłoszeń (alternatywa do antyzłączenia).
SELECT o.id FROM admissions_offer o
WHERE NOT EXISTS (SELECT 1 FROM admissions_application a WHERE a.offer_id=o.id);

-- Q07: ostatnia opublikowana wersja w każdej turze.
SELECT DISTINCT ON (offer_id,round_id) offer_id,round_id,version,cutoff,qualified_count
FROM admissions_publication ORDER BY offer_id,round_id,version DESC;

-- Q08: indeks funkcyjny; parametr musi odpowiadać wyrażeniu indeksu.
EXPLAIN (ANALYZE, BUFFERS)
SELECT id,name FROM admissions_program WHERE lower(name)=lower('Informatyka');

-- Q09: GIN jsonb_path_ops; wyszukiwanie w niezmiennym obrazie danych zgłoszenia.
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM admissions_application WHERE input_snapshot @> '{"diploma":"inżynier"}'::jsonb;

-- Q10: zgodność utrzymywanej projekcji z danymi źródłowymi — wynik powinien być pusty.
SELECT o.id FROM admissions_offer o LEFT JOIN pk_offer_stats s ON s.offer_id=o.id
WHERE ROW(coalesce(s.applications,0),coalesce(s.verified,0),coalesce(s.confirmed,0))
  IS DISTINCT FROM (SELECT ROW(count(*),count(*) FILTER(WHERE a.status='verified'),count(*) FILTER(WHERE a.status='confirmed'))
                   FROM admissions_application a WHERE a.offer_id=o.id);

-- Q11: odczyt audytu wierszowego i instrukcji SQL, bez ujawniania haseł.
SELECT occurred_at,transaction_id,db_actor,operation,application_id,before_state,after_state
FROM pk_row_audit ORDER BY occurred_at DESC LIMIT 30;
SELECT * FROM pk_statement_audit ORDER BY id DESC LIMIT 30;

-- Q12: funkcja dziedzinowa zgodna z limitowaniem WR (portfolio podstawiane wcześniej).
SELECT pk_wr(100,95,95,50) AS wynik_z_limitem;

-- DBA, tylko gdy potrzebne: odbudowa projekcji po wykryciu rozbieżności.
-- CALL pk_reconcile_offer_stats();
