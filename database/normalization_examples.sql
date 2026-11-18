-- Przykłady do omówienia na demonstracyjnej bazie projektu. Zapytania nie modyfikują danych.
BEGIN READ ONLY;

-- 1NF: ciąg wyników do prezentacji nie pozwala osobno ograniczyć poziomu, przedmiotu i wartości.
-- ExamResult zapisuje każdą wartość atomowo i ma UNIQUE(user_id, subject, level).
SELECT string_agg(e.subject || ' / ' || e.level || ': ' || e.value, '; ' ORDER BY e.subject, e.level)
       AS postac_przed_1nf
FROM admissions_examresult e JOIN admissions_user u ON u.id=e.user_id
WHERE u.email='kandydat@demo.local';

SELECT e.user_id, e.subject, e.level, e.value
FROM admissions_examresult e JOIN admissions_user u ON u.id=e.user_id
WHERE u.email='kandydat@demo.local'
ORDER BY e.subject, e.level;

-- 2NF: w hipotetycznej relacji z kluczem (user, subject, level) nazwisko zależy tylko od user.
-- Pierwszy SELECT pokazuje liczbę powtórzeń nazwiska w takim spłaszczeniu.
SELECT u.id AS user_id, u.last_name, count(*) AS powtorzenia_nazwiska
FROM admissions_user u JOIN admissions_examresult e ON e.user_id=u.id
WHERE u.email='kandydat@demo.local'
GROUP BY u.id, u.last_name;

-- 3NF: offer_id -> program_id -> faculty_id -> faculty_name.
-- Tyle wierszy trzeba byłoby zmienić po zmianie nazwy wydziału w spłaszczonym katalogu.
SELECT f.code AS wydzial, f.name AS nazwa, count(*) AS oferty_z_powtorzona_nazwa
FROM admissions_offer o
JOIN admissions_program p ON p.id=o.program_id
JOIN admissions_faculty f ON f.id=p.faculty_id
WHERE o.campaign_id=(SELECT id FROM admissions_campaign ORDER BY start, id LIMIT 1)
GROUP BY f.id ORDER BY f.code;

-- 4NF: dwa przedmioty i dwie kwalifikacje konkretnej oferty dają cztery wiersze.
-- Dwa niezależne zbiory faktów pozostają w AllowedSubject i AllowedProfession.
WITH offer AS (
  SELECT id FROM admissions_offer o
  WHERE 2 <= (SELECT count(*) FROM admissions_allowedsubject s WHERE s.offer_id=o.id)
    AND 2 <= (SELECT count(*) FROM admissions_allowedprofession p WHERE p.offer_id=o.id)
  ORDER BY id LIMIT 1
), subjects AS (
  SELECT s.offer_id, s.subject FROM admissions_allowedsubject s JOIN offer o ON o.id=s.offer_id
  ORDER BY s.subject LIMIT 2
), professions AS (
  SELECT p.offer_id, p.name FROM admissions_allowedprofession p JOIN offer o ON o.id=p.offer_id
  ORDER BY p.name LIMIT 2
)
SELECT s.offer_id, s.subject, p.name AS kwalifikacja
FROM subjects s JOIN professions p ON p.offer_id=s.offer_id
ORDER BY s.subject, p.name;

-- 5NF: dalsza projekcja relacji AllowedProfession do dwóch list zgubi powiązanie.
-- Takie złączenie odtworzyłoby pary, których nie ma w regułach ofert.
WITH assignments AS (
  SELECT ap.offer_id, ap.name
  FROM admissions_allowedprofession ap JOIN admissions_offer o ON o.id=ap.offer_id
  WHERE o.campaign_id=(SELECT id FROM admissions_campaign ORDER BY start, id LIMIT 1)
), wrong_pairs AS (
  SELECT o.offer_id, p.name FROM (SELECT DISTINCT offer_id FROM assignments) o
  CROSS JOIN (SELECT DISTINCT name FROM assignments) p
  EXCEPT SELECT offer_id, name FROM assignments
)
SELECT count(*) AS bledne_pary_po_projekcji FROM wrong_pairs;

-- BCNF: w złączeniu Identity+Exam klucze to (user,subject,level) oraz (pesel,subject,level).
-- user -> pesel ma kluczowy atrybut po prawej (3NF), lecz wyznacznik nie jest nadkluczem (brak BCNF).
-- Rozkład na Identity(user,pesel) i Exam(user,subject,level,value) zachowuje te zależności.
SELECT e.user_id,i.pesel,e.subject,e.level,e.value
FROM admissions_examresult e JOIN admissions_candidateidentity i ON i.user_id=e.user_id
WHERE e.user_id=(SELECT id FROM admissions_user WHERE email='kandydat@demo.local');

-- 6NF: aktualny telefon, portfolio i e-mail są fizycznie osobnymi relacjami faktów.
-- Brak telefonu nie powoduje utraty wiersza kandydata ani jego pozostałych faktów.
SELECT u.id, c.value AS phone, p.value AS portfolio_url, n.value AS notification_email,
       a.value AS srednia, d.title AS tytul
FROM admissions_user u
LEFT JOIN admissions_candidatephone c ON c.user_id=u.id
LEFT JOIN admissions_candidateportfolio p ON p.user_id=u.id
LEFT JOIN admissions_candidatenotificationaddress n ON n.user_id=u.id
LEFT JOIN admissions_academicaverage a ON a.user_id=u.id
LEFT JOIN admissions_diploma d ON d.user_id=u.id
WHERE u.email='kandydat@demo.local';

COMMIT;
