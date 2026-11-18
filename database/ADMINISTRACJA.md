# Instrukcja administratora bazy i serwera

## Lokalizacja i odpowiedzialność

Serwer jednej instancji przechowuje runtime/postgres, runtime/documents, runtime/local.json oraz kopie. Po odtworzeniu aktywna nazwa bazy i ścieżka dokumentów mogą być inne; odczytuje je portable.environment. Nie udostępniaj pliku local.json klientom. Klient LAN otrzymuje profil połączenia HTTPS i certyfikat CA, bez hasła PostgreSQL.

pk_owner jest właścicielem schematu i stosuje migracje. pk_app obsługuje API. Inicjalizacja nadaje prawa oraz odbiera bezpośrednią modyfikację chronionych obiektów. Kontakt jest zapisywany przez widok i wyzwalacz, a nie bezpośrednio do jego tabel faktów. Pracownikom aplikacji nadaje się role aplikacyjne; nie dostają kont administratora bazy.

## Uruchomienie i migracje

Wersja źródłowa: python start.py --setup, potem python start.py. Pakiet Windows: Uruchom.bat albo RekrutacjaPK.exe. Pierwszy start uruchamia lokalny klaster i migracje. Do pracy LAN wybierz „Serwer dla zespołu”, a na stacji „Połącz z serwerem”; szczegóły opisuje KLIENT-SERWER.md.

Przed aktualizacją zamknij użytkowników, wykonaj kopię, zachowaj poprzednie wydanie i sprawdź aktualizację na kopii. Migracja 0011 wykonuje dwukierunkowe porównanie kontaktów; niezgodność wycofuje całą transakcję. Odtworzenie starej kopii nie jest cofnięciem plików programu; po uruchomieniu nowej wersji zostaną zastosowane jej migracje.

Eksport modelu: python start.py --export-model po zamknięciu aplikacji tej instancji. Wynik w runtime/models zawiera metadane, nie dane osobowe. Polecenie stosuje aktualne migracje i sprawdza wszystkie rekonstrukcje.

## Konsola DBA i kontrola

Gdy działa serwer, konsolę otwiera się narzędziem vendor/pgsql/bin/psql.exe, host 127.0.0.1, port db_port z lokalnej konfiguracji, właściciel pk_owner, aktywna baza z konfiguracji. Użyj opcji -W, aby hasło podać interaktywnie. Nie zapisuj hasła w historii poleceń ani dokumentacji.

Podstawowe polecenia psql:
- \dt i \dv — tabele oraz widoki;
- \d+ admissions_candidatephone — typy, klucze i ograniczenia;
- \df pk_* — funkcje; \dfp — procedury;
- \dp — uprawnienia;
- SELECT * FROM pg_stat_activity WHERE datname=current_database(); — sesje;
- SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public'; — indeksy;
- SELECT * FROM django_migrations WHERE app='admissions' ORDER BY applied; — migracje.

Uprawnienia można sprawdzić przez has_table_privilege('pk_app','pk_row_audit','UPDATE') oraz has_table_privilege('pk_app','admissions_candidatecontact','UPDATE'). Oczekiwane wartości to odpowiednio false i true.

Zapytanie Q10 z queries.sql porównuje wszystkie trzy liczniki z agregacją zgłoszeń; pusty wynik oznacza zgodność. Gdy administrator rozpozna przyczynę rozbieżności, może wykonać CALL pk_reconcile_offer_stats(); i ponownie Q10. Nie wyłączaj wyzwalaczy aplikacji w celu przyspieszenia zwykłego zapisu.

Pełne plany zbiera EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON). ANALYZE wykonuje badane polecenie, więc DML mierz na kopii lub w transakcji zakończonej ROLLBACK. Trzy gotowe eksperymenty tworzą tabele TEMP. Nie stosuj CLUSTER w trakcie obsługi użytkowników; wymaga wyłącznej blokady.

## Kopia i odtworzenie

1. Administrator aplikacji otwiera Administrację i tworzy kopię bazy oraz dokumentów.
2. Zachowuje ZIP, datę i manifest z SHA-256 oraz liczebnościami. Sama kopia plików działającego klastra nie jest zamiennikiem pg_dump.
3. Przenosi kopię na drugi nośnik lub host zgodnie z ustaloną organizacją przechowywania.
4. Po zamknięciu programu wykonuje python start.py --restore "ścieżka-do-kopii.zip" albo odpowiadającą operację w pakiecie.
5. Mechanizm sprawdza archiwum, sumy i liczebności, odtwarza do nowej bazy i nowego katalogu dokumentów, a następnie przełącza aktywną instancję.
6. Po starcie sprawdza logowanie, pobranie dokumentu, statusy i historyczne wyniki. Odtworzone oczekujące e-maile są anulowane, żeby nie wysłać ich ponownie.

tools/e2e_smoke.py wykonuje tę procedurę na izolowanym zbiorze i sprawdza dane po odtworzeniu. Warunek N09 wynosi 30 minut dla zestawu demonstracyjnego. Produkcyjne RPO/RTO i retencję trzeba uzgodnić z operatorem; obecne narzędzie nie jest usługą HA.

## Dane testowe i błędy uruchomienia

Scenariusze „Administracja” wykonuj na kontach demonstracyjnych. Pełny test regresji uruchamia się przez python start.py --test, a przebieg klienta przez python tools/e2e_smoke.py --https. Do testów ustaw osobny PK_DATA_DIR; e2e_smoke robi to sam.

Log serwera znajduje się w runtime/application.log, a błędy wejścia w runtime/error.log. Przy zajętym porcie lokalne API wybiera wolny i przekazuje go klientowi. W razie błędu migracji zachowaj log i kopię; komunikatu nie naprawia się usuwaniem działającego katalogu runtime.
