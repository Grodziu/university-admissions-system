# Terminologia indeksów a PostgreSQL 17

Opis dotyczy PostgreSQL 17 używanego przez aplikację. Dostępność mechanizmu w silniku i użycie konkretnego indeksu przez optymalizator to dwie różne kwestie.

| Termin | PostgreSQL i decyzja w projekcie |
|---|---|
| Zwykły B-tree, złożony | Dostępne; PK/UNIQUE, kolejka oferty, historia kandydata i kolejność rankingu |
| Indeks funkcyjny | Indeks wyrażenia, np. lower(name); predykat SELECT musi odpowiadać wyrażeniu |
| Częściowy | Indeks tylko stanów kwalifikacji; ogranicza liczbę indeksowanych wierszy |
| Pokrywający | INCLUDE przechowuje dodatkowe wartości; Index Only Scan wymaga również spełnienia warunków widoczności MVCC |
| IOT (index-organized table) | PostgreSQL przechowuje heap oddzielnie od indeksów. INCLUDE i Index Only Scan mogą ograniczyć odczyt heap, ale nie tworzą IOT |
| Indeks bitmapowy | Brak natywnej metody CREATE INDEX ... USING bitmap. Bitmap Index/Heap Scan to plan budujący bitmapę lokalizacji wierszy podczas wykonania |
| Klastrowy / klaster indeksowy | CLUSTER jednorazowo porządkuje heap według indeksu; kolejne zapisy nie zachowują tego porządku. Nie jest to stale utrzymywane IOT ani wspólny klaster kilku tabel |
| Reverse key | Brak natywnego odpowiednika Oracle REVERSE. B-tree na reverse(reference) jest indeksem wyrażenia na odwróconym tekście, ze zmienionym warunkiem równości; nie jest odwróceniem bajtów klucza Oracle |
| Odwrócony (inverted) | GIN odwzorowuje składniki wartości na wiersze, np. JSONB. „Odwrócony indeks” GIN i „odwrócony klucz” REVERSE to inne pojęcia |
| Kompresja kluczy | B-tree stosuje własne mechanizmy, m.in. deduplikację powtarzających się kluczy. Nie deklarujemy równoważności z Oracle KEY COMPRESSION. INCLUDE wyłącza deduplikację B-tree |
| Rosnący/malejący | ASC/DESC i skan wsteczny; kolejność DESC nie jest reverse key |
| Domenowy | Oracle domain index to rozszerzalny mechanizm indeksowania. PostgreSQL oferuje klasy operatorów/metody dostępu i rozszerzenia. CREATE DOMAIN definiuje dziedzinę wartości, nie indeks domenowy |
| Inne metody | Hash dla równości; GiST/SP-GiST dla odpowiednich klas operatorów; BRIN dla korelacji wartości z blokami. W aplikacji działa BRIN czasu audytu oraz GIN obrazu JSONB |

Podstawy: [typy indeksów](https://www.postgresql.org/docs/17/indexes-types.html), [CREATE INDEX](https://www.postgresql.org/docs/17/sql-createindex.html), [mechanizmy indeksów Oracle](https://docs.oracle.com/en/database/oracle/oracle-database/21/cncpt/indexes-and-index-organized-tables.html).

## Dowody i ograniczenia

W migracji 0002 występują application_verified_partial, application_snapshot_gin, audit_time_brin i program_lower_name. Pozostałe indeksy tworzą migracje modeli. Eksport schema.sql oraz models/model-catalog.json opisują aktualny schemat, a benchmark.py mierzy odczyt i cenę zapisu z dodatkowym indeksem.

index_capabilities.py wykonuje na 100 000 wierszy TEMP:
1. B-tree i zapytanie OR; zapisuje rzeczywisty plan bitmapowy, jeżeli wybierze go optymalizator, bez wymuszania skanu.
2. B-tree na reverse(reference), sprawdzenie identyczności równości i plan.
3. CLUSTER i wstawienie nowego najniższego klucza na końcu fizycznym tabeli — porządek nie jest automatycznie utrzymywany.
4. Porównanie rozmiaru B-tree przy włączonej/wyłączonej deduplikacji.

To przykłady możliwości silnika na kopii, a nie dodatkowe indeksy obciążające bazę użytkownika. Wymaganie analizowania IOT/bitmap/reverse realizuje porównanie technologiczne i zbadanie dostępnych odpowiedników; nie przypisujemy PostgreSQL obiektów Oracle, których nie implementuje. Jeżeli odbiór wymagałby literalnie obiektu Oracle IOT, konieczny byłby osobny wariant Oracle.

[Bitmapy planu](https://www.postgresql.org/docs/17/indexes-bitmap-scans.html) tworzone są w czasie zapytania. [CLUSTER](https://www.postgresql.org/docs/17/sql-cluster.html) jest operacją jednorazową i blokuje tabelę. [Index Only Scan](https://www.postgresql.org/docs/17/indexes-index-only-scans.html) nadal zależy od mapy widoczności. [GIN](https://www.postgresql.org/docs/17/gin.html) służy wartościom składającym się z wielu indeksowanych elementów. Deduplikację opisuje [implementacja B-tree](https://www.postgresql.org/docs/17/btree.html).

## Procedury i wyzwalacze

PostgreSQL używa PL/pgSQL zamiast Oracle PL/SQL; procedury SQL także są dostępne. pk_reconcile_offer_stats jest procedurą wywoływaną przez CALL. Funkcje wyzwalaczy zwracają trigger, a nie są procedurami wywoływanymi przez CALL.

Wyzwalacz wierszowy obsługuje pojedyncze zgłoszenie i korektę liczników, instrukcyjny odczytuje transition tables, a INSTEAD OF na widoku kontaktu przekłada zapis na relacje faktów. [CREATE TRIGGER](https://www.postgresql.org/docs/17/sql-createtrigger.html) określa te różnice. Sam zapis słowa PROCEDURE w historycznej składni CREATE TRIGGER nie zmienia funkcji w procedurę.
