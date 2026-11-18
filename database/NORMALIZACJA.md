# Model danych, zależności i normalizacja

Stan odniesienia: migracja 0011, wydanie 0.7.0. Rozpatrujemy odrębnie model pojęciowy, model logiczny pojedynczych faktów i fizyczny schemat obsługujący aplikację.

Wydanie 0.8.0 zachowuje ten sam schemat danych. Moduł wykładowców ma odrębny, wersjonowany katalog informacyjny; nie dodaje tabel do procesu rekrutacji.

## Wynik i granice

Dane kontaktowe zostały fizycznie rozłożone do 6NF. Klient i serwer nadal używają CandidateContact, który jest teraz zapisywalnym widokiem. Migracja porównuje stary i odtworzony zbiór w obu kierunkach; różnica powoduje wycofanie całej migracji.

Dla wszystkich tabel bazy istnieje generowany model logiczny 6NF: kotwica istnienia encji oraz osobne relacje klucz–wartość. Plik models/model-6nf.sql buduje ten model, a model_export.py wypełnia go w wycofywanej transakcji i sprawdza rekonstrukcję każdej tabeli przez EXCEPT ALL w obu kierunkach. Model obejmuje też techniczne tabele Django; są oznaczone oddzielnie w katalogu.

Schemat operacyjny zachowuje wieloatrybutowe tabele, wersjonowane obrazy historyczne i projekcję liczników. To jawne wybory fizyczne. Weryfikacja na danych potwierdza poprawność konkretnego przekształcenia; dowód dla dowolnego dopuszczalnego stanu wynika z zależności i sposobu konstrukcji podanych niżej.

## Intencja, ekstensja i typy atrybutów

Intencją jest definicja relacji wraz z dziedzinami, kluczami i regułami, np. „jeden wynik danego przedmiotu i poziomu na kandydata”. Ekstensją jest jej aktualny zbiór wierszy. Przypadkowa równość danych demonstracyjnych nie ustanawia zależności funkcyjnej.

| Rodzaj | Przykład i odwzorowanie |
|---|---|
| Prosty | Nazwa wydziału: varchar; liczba miejsc: dodatnia liczba całkowita |
| Złożony | Adres: city, street, building, apartment, postal_code w Residence; części są osobno walidowane |
| Wielowartościowy | Wyniki egzaminów, dokumenty, wersje zdjęć, wydziały współprowadzące: odrębne wiersze i związki |
| Pochodny | WR, odległość, liczniki; obliczanie lub jawnie utrzymywana projekcja |
| Opcjonalny | Brak średniej/zdjęcia przed uzupełnieniem; brak wiersza faktu albo NULL w schemacie operacyjnym |
| Historyczny | Publication, RankingEntry i wersje dokumentów; zmiana profilu nie przepisuje starej decyzji |
| Dokument złożony | JSONB input_snapshot i explanation są typowanymi obrazami dokumentów decyzji; nie zastępują bieżących relacyjnych wyników |
| Identyfikator | bigint jako klucz techniczny; UUID zgłoszenia do adresowania publicznego; kod akademika jako klucz naturalny |

JSONB uznajemy za pojedynczą wartość dziedziny dokumentów w tym modelu. Analiza jego wewnętrznych pól wymagałaby osobnego modelu dokumentu. Ta decyzja nie jest dowodem, że tablica wyników w JSON zastępuje normalizację relacyjnego profilu.

Nie zakładamy zależności kod_pocztowy → miasto ani nazwisko → osoba. Telefon i adres e-mail powiadomień nie są kluczami osób.

## Encje, związki i decyzje

| Decyzja | Wariant odrzucony i uzasadnienie |
|---|---|
| Program oraz Offer | Sam Program z limitami nadpisywałby parametry różnych edycji, stopni i trybów |
| Campaign i Round | Globalny numer tury nie opisuje równoległych harmonogramów I, II i PG |
| Application: UNIQUE(candidate,offer) | Oddzielny wiersz przy każdym ponowieniu tworzyłby kilka zgłoszeń na tę samą ofertę |
| Faculty wiodący oraz tabela współprowadzenia | Jeden tekst z nazwami utrudnia FK; same wydziały partnerskie nie wskazują odpowiedzialnego wydziału |
| ProfileDocument i Document | Profil jest aktualny, a zgłoszenie musi zachować wersję ocenianą przez komisję |
| Publication i RankingEntry | Nadpisanie wyniku usuwałoby historię publikacji i korekt |
| ContactAnchor i trzy fakty | Tabela czterokolumnowa była w BCNF przy user_id → pozostałe pola, ale miała nietrywialną dekompozycję złączeniową |
| AllowedSubject i AllowedProfession | Niezależne zbiory nie powinny być przechowywane jako ich iloczyn |
| Role jako dyskryminator User | Kandydat/komisja/administrator to role dostępu; nie stworzono fikcyjnej hierarchii tabel dziedziczenia |
| Audyt i wersje | Historia zdarzeń jest dopisywana; nie deklarujemy pełnej bitemporalności ani odtwarzania każdego pola profilu na dowolną datę |

Użytkownik może istnieć przed uzupełnieniem profilu: User 1 — 0..1 ContactAnchor, Identity, Residence, AcademicAverage i Diploma. Kotwica kontaktu ma 0..1 telefon, portfolio i adres powiadomień. Program ma dokładnie jeden wydział wiodący i dowolną liczbę partnerskich. Oferta wskazuje jeden program i nabór, ma wiele dopuszczonych przedmiotów i zgłoszeń. Zgłoszenie ma jednego kandydata, ofertę i turę; dokumenty oraz publikacje są wersjonowane. Samoodwołanie Document.reused_from opisuje pochodzenie kopii.

Pełne atrybuty, typy, PK, FK, UNIQUE, CHECK i NULL są w models/model-catalog.json oraz schema.sql. Diagram fizyczny: models/model.dbml lub models/model.mmd. UML rzeczywistych klas: models/classes.puml.

## Zależności i kolejne postacie normalne

Rozkłady wykonujemy na projekcjach dziedziny systemu. Nie przypisujemy całej bazie jednej postaci na podstawie wybranego SELECT.

### UNF → 1NF

Prezentacyjny zapis „matematyka/basic:90;informatyka/extended:88” zawiera grupę powtarzalną. Rozkład daje ExamResult(user_id,subject,level,value), klucz K=(user_id,subject,level), K → value. Jedna wartość procentowa dotyczy jednego przedmiotu i poziomu. W źródłowej aplikacji występuje również techniczne id i UNIQUE(K).

Anomalia: w ciągu tekstowym nie można kluczem wykluczyć drugiego wyniku tego samego egzaminu. Po rozkładzie unikalność i zakres 0–100 egzekwuje baza.

### 1NF → 2NF

Spłaszczona relacja R(user_id,subject,level,value,last_name) ma klucz K oraz user_id → last_name. Nazwisko zależy od właściwej części K. Rozkład:
- U(user_id,last_name), klucz user_id;
- E(user_id,subject,level,value), klucz K.

Przecięcie projekcji to user_id i user_id → U, zatem rozkład binarny jest bezstratny. Obie pierwotne zależności pozostają lokalne. Zmiana nazwiska jednego wiersza powoduje sprzeczność; usunięcie ostatniego egzaminu usuwa jedyne nazwisko; zapis osoby bez egzaminu wymagałby pustych części klucza. Właściwy User istnieje niezależnie od ExamResult.

### 2NF → 3NF

R(offer_id,program_id,faculty_id,faculty_name), klucz offer_id, zależności:
offer_id → program_id; program_id → faculty_id; faculty_id → faculty_name.
Klucz jest jednoatrybutowy, więc brak zależności częściowych. Nazwa wydziału zależy przechodnio od klucza.

Rozkład O(offer_id,program_id), P(program_id,faculty_id), F(faculty_id,faculty_name) jest bezstratny: kolejne przecięcia są kluczami dołączanych relacji. Zachowuje wszystkie trzy zależności. Nazwę wydziału zmieniamy w jednym F, a jego istnienie nie wymaga oferty.

### 3NF → BCNF: rzeczywisty przykład z dwoma kluczami

R(user_id,pesel,subject,level,value) powstaje przez połączenie CandidateIdentity z ExamResult.
F={user_id → pesel, pesel → user_id, (user_id,subject,level) → value}.
Klucze kandydujące: K1=(user_id,subject,level), K2=(pesel,subject,level). Wszystkie kolumny poza value są atrybutami kluczowymi. R spełnia 3NF: prawa strona zależności user_id ↔ pesel jest atrybutem kluczowym, a value zależy od klucza.

R nie spełnia BCNF: user_id → pesel, lecz samo user_id nie identyfikuje egzaminu. Rozkład Identity(user_id,pesel) i Exam(user_id,subject,level,value) jest bezstratny (wspólne user_id wyznacza Identity) i zachowuje zależności; pesel → user_id wynika z UNIQUE w Identity. Nie opieramy tego przykładu na założeniu, że nazwisko identyfikuje prowadzącego.

### BCNF → 4NF

Dla oferty dopuszczone przedmioty i zawody są niezależnymi zbiorami. Hipotetyczna relacja T(offer_id,subject,profession) przechowuje ich iloczyn. Zakładamy brak dodatkowych FD poza pełnym kluczem; relacja jest w BCNF. Występuje nietrywialna MVD offer_id →→ subject oraz niezależnie offer_id →→ profession, a offer_id nie jest nadkluczem T.

Rozkład S(offer_id,subject), P(offer_id,profession) jest bezstratny na mocy tej MVD. Dwa przedmioty i dwa zawody tworzą cztery trójki zamiast dwóch niezależnych list. Dodanie zawodu wymagałoby powtórzenia go dla każdego przedmiotu. W aplikacji listy są od początku oddzielne.

Przykład iloczynu obejmuje oferty z oboma niepustymi zbiorami. Dla oferty bez zawodów INNER JOIN da pusty wynik i nie jest sposobem odtwarzania listy przedmiotów; odczytujemy niezależne zbiory od kotwicy Offer. Nie wyciągamy zależności o opcjonalnych faktach z pustego iloczynu.

### 4NF → 5NF

Po poprzednim rozkładzie relacje S i P są binarnymi faktami przypisania. Przy braku dodatkowej reguły kompletnego iloczynu nie mają nietrywialnej JD. Już spełniają 5NF. Rozbicie AllowedProfession na osobną listę ofert i listę zawodów daje po CROSS JOIN nieuprawnione pary; normalization_cases.py wylicza ich liczbę na rzeczywistych regułach ofert.

Nie wymyślamy trójargumentowej reguły „każda zgodna para oznacza zgodną trójkę”, której produkt nie realizuje. Przejście do kolejnej postaci może polegać na wykazaniu, że dalszy rozkład nie jest potrzebny.

### 5NF → 6NF

Dla starego C(u,phone,portfolio_url,notification_email), klucz u, zachodzą u → phone, u → portfolio_url, u → notification_email. Relacja jest w BCNF i, przy tych założeniach, w 5NF: zależności złączeniowe wynikają z klucza. Nie jest w 6NF, ponieważ istnieje nietrywialna JD:
*C{(u,phone),(u,portfolio_url),(u,notification_email)}.

Dla wartości określonych C = π(u,phone)(C) JOIN π(u,portfolio_url)(C) JOIN π(u,notification_email)(C). Każde dołączenie ma przecięcie {u}, będące kluczem. Nie powstają dodatkowe kombinacje. Każda wynikowa relacja ma jeden fakt zależny od klucza i brak nietrywialnej JD w przyjętej intencji. Rozdzielenie jej na dwie projekcje unarne straciłoby powiązanie, np. {(u1,a),(u2,b)} odtworzyłoby też (u1,b) i (u2,a).

W SQL dodatkowo zachowujemy ContactAnchor(u), żeby osoba bez żadnego opcjonalnego faktu nie zniknęła. Brak faktu reprezentuje brak wiersza, a widok stosuje LEFT JOIN lub równoważne podzapytanie skalarne. Puste pole GUI odtwarza dopiero COALESCE(...,'') na granicy zgodności. To jawna reprezentacja opcjonalności, a nie klasyczny dowód oparty na porównywaniu NULL.

Dla każdej pozostałej relacji R(k,a1,...,an) model referencyjny stosuje tę samą regułę: A(k) i Fi(k,ai). Indukcyjnie każde dołączenie jest bezstratne dzięki k → ai. Zachowujemy kotwicę oraz typy wartości. PK z katalogu wystarcza do tego dowodu; wszystkie dodatkowe klucze i reguły są osobnymi ograniczeniami intencji.

**Zachowanie zależności nie jest tym samym co bezstratność.** Alternatywne UNIQUE i CHECK obejmujące kilka faktów, np. minimum ≤ capacity, nie stają się lokalnymi ograniczeniami pojedynczej tabeli Fi. Są zapisane w katalogu i egzekwowane w schemacie operacyjnym. Referencyjny schemat jest odczytowy. Samodzielne udostępnienie w nim zapisu wymagałoby walidacji rekonstrukcji lub constraint triggers; plik model-6nf.sql nie jest migracją zastępującą cały serwer.

### DKNF — odrębne kryterium

DKNF wymaga, by wszystkie ograniczenia wynikały z dziedzin i kluczy; nie jest kolejnym szczeblem między numerowanymi NF. Dla AcademicAverage(user_id,value), z ustaloną dziedziną 2..5 i kluczem user_id, lokalne ograniczenia mają taką postać. Cały system nie spełnia DKNF: zgodność zatwierdzonej wpłaty z opłatą oferty oraz reguły tury wymagają reguł między relacjami. Realizują je funkcje wyzwalaczy i transakcje. Podniesienie postaci normalnej nie usuwa tych wymagań.

## Model logiczny a fizyczny

| Odstępstwo | Cel | Kontrola |
|---|---|---|
| Wieloatrybutowe Offer, Residence, Application itd. | Mniej złączeń i prostsze transakcje Django; wartości pozostają w jednym spójnym agregacie zapisu | Pełny rozkład referencyjny, katalog ograniczeń i testy integralności |
| CandidateContact jako widok | Zachowanie interfejsu klienta i kontraktu ORM po rzeczywistej zmianie przechowywania | INSTEAD OF INSERT/UPDATE/DELETE, blokada kotwicy, wycofanie transakcji, test równoległych pól |
| JSONB wersji decyzji | Historyczny materiał do odtworzenia wyniku | Publikacje niezmienne, wersje reguł i dokumentów |
| pk_offer_stats | Odczyt liczników bez ponownej agregacji | Wyzwalacz wierszowy i pk_reconcile_offer_stats, porównanie wszystkich trzech liczników |
| Kopia katalogu w eksperymencie denormalizacji | Jawny przykład naruszenia 2NF/3NF i jego kosztu | Tabele TEMP, wyzwalacze wierszowe/instrukcji, identyczność wyników po każdej modyfikacji |

W dn_catalog(offer_id,subject,program_id,program_name,faculty_id,faculty_name) klucz to (offer_id,subject). offer_id → program_id i nazwy jest zależnością częściową; program_id → faculty_id → faculty_name jest zależnością przechodnią. Ta kopia rzeczywiście narusza 2NF i 3NF. Sam licznik przypisany do klucza oferty nie byłby takim dowodem. Eksperyment nie wprowadza redundantnych nazw do krytycznej ścieżki zapisu produkcyjnego programu.

## Odtwarzanie dowodów

- python start.py --export-model: model, katalog i porównanie wszystkich rekonstrukcji w runtime/models.
- python start.py --benchmark-denormalization: czasy, plany, poprawność i narzut INSERT/UPDATE/DELETE.
- python start.py --benchmark: wpływ indeksu, osobno koszt wstawiania.
- python start.py --benchmark-query: tylko zmiana SELECT, te same dane i indeksy.

Uruchamiaj pomiary na kopii demonstracyjnej. Wszystkie tabele eksperymentów są tymczasowe lub model powstaje w wycofywanej transakcji. Wynik 6NF to dowód konstrukcyjny plus sprawdzony stan danych; pomiar SQL nie zastępuje pomiaru API ani testu sieci.
