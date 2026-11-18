# Baza wymagań — Rekrutacja PK 1.0

Identyfikatory wiążą specyfikację z implementacją i testami. MUST oznacza warunek odbioru końcowego, SHOULD ważny element jakościowy. Zmiany kryteriów mają datę, uzasadnienie i przypisany sposób weryfikacji.

## 20 wymagań funkcjonalnych

| ID | MoSCoW | Wymaganie i sprawdzalny warunek odbioru | Implementacja |
|---|---|---|---|
| F01 | MUST | Rejestracja, logowanie, wylogowanie i odzyskanie dostępu jednorazowym kodem. TOTP można włączyć oraz wyłączyć hasłem i aktualnym kodem; odzyskanie unieważnia stare sesje, wyłączenie TOTP pozostałe sesje. | api.py, auth.py |
| F02 | MUST | Role Kandydat, Komisja i Administrator; kandydat nie odczyta ani nie zmieni cudzych dokumentów/zgłoszeń przez API. Administrator zmienia rolę innego konta. | `services.require_staff`, autoryzacja API |
| F03 | MUST | Jedna karta na kierunek i stopień, z wyborem trybu. Filtry obejmują nazwę, stopień, tryb i wydział. Kandydat widzi opis, sylabus, zasady, terminy i semestralną kwotę przykładową dla płatnych trybów. Komisja ma stan publikacji, limit, minimum i potwierdzone miejsca. | `api.catalog`, `desktop/discover.py` |
| F04 | MUST | Oferty mają parametry naboru i harmonogram 3/2/2 tur o wspólnym końcu. Przed pierwszą turą danego stopnia komisja i administrator tworzą ofertę i zmieniają warunki naboru do czasu pierwszego zgłoszenia. Nową edycję i scenariusze demo uruchamia administrator. | `offers.py`, `Campaign`, `Round`, `Offer`, `restart_campaign` |
| F05 | MUST | Rejestracja i profil wymagają unikatowego PESEL z poprawną datą i cyfrą kontrolną, telefonu i adresu zamieszkania. Profil zapisuje także wyniki matury lub kwalifikacji, tytuł i średnią. PESEL trafia do prywatnej tabeli tożsamości, a zgłoszenie utrwala dane potrzebne do wyjaśnienia wyniku. | `profiles.py`, `CandidateIdentity`, `Residence`, `input_snapshot` |
| F06 | MUST | Kandydat zapisuje szkic i składa jedno zgłoszenie na ofertę; ponowienie żądania nie duplikuje rekordu ani chwili złożenia. | `create_application`, `submit` |
| F07 | MUST | Zdjęcie i dokumenty wielokrotnego użytku mają wersje w profilu. Zgłoszenie utrwala wersję odpowiednich załączników przy złożeniu. Potwierdzenie wpłaty jest przypisane do zgłoszenia. Akceptacja zdjęcia działa dla sprawdzonej wersji, którą ślubowanie zapisuje w historii. | `ProfilePhoto`, `ProfileDocument`, `Document`, `review`, `take_oath` |
| F08 | MUST | Zatwierdzenie opłaty wymaga dowodu i zgodnej kwoty. Zaznaczenie zgodności wyłącza pole innej kwoty w GUI, a API odrzuca sprzeczne dane. Inną kwotę zapisuje się przy zwrocie lub odrzuceniu. | `submit`, `review`, trigger kwoty |
| F09 | MUST | Komisja akceptuje, odrzuca lub zwraca zgłoszenie z uzasadnieniem. Zbiorcza akceptacja pokazuje gotowe pozycje i powody pominięcia. Portfolio obowiązkowe sprawdzane jest według konkretnej oferty, premie według zgłoszenia. Zachowane są filtry. | `review`, `batch_operation`, `desktop/flows.py` |
| F10 | MUST | I stopień: WR do 1000, D=0/10/20/30/40/50 według katalogu osiągnięć projektu, wyróżnienie portfolio podnosi P2. II stopień: wyłącznie średnia. Podyplomowe: kolejność kompletnych zgłoszeń i dyplom co najmniej I stopnia. | domain.py, policies.py, testy granic |
| F11 | MUST | Komisja filtruje oferty według nazwy, wydziału, stopnia i trybu oraz otwiera ranking roboczy aktualizowany co 5 s. Publikacja następuje po zamknięciu i rozpatrzeniu zgłoszeń. Współbieżna publikacja tworzy jedną wersję, a remisy przyjmujemy w całości. | `ranking_preview`, `publish`, `batch_operation`, `page_ranking` |
| F12 | MUST | Kandydat widzi etapy i najbliższą czynność. Karta wyniku pokazuje składniki, wzór i wersję. Pulpit pracowników pokazuje liczbę osób, zgłoszeń, spraw oczekujących, potwierdzeń i zainteresowanie kierunkami według tur. | `api.workspace`, pulpit, harmonogram, `ScoreCard` |
| F13 | MUST | Rezerwowy/nieprzyjęty może ponownie złożyć zgłoszenie w następnej turze; już potwierdzone miejsca zmniejszają dostępną pulę. | `candidate_decision('continue')`, `publish` |
| F14 | MUST | Kandydat potwierdza miejsce lub wycofuje zgłoszenie. Brak potwierdzenia wygasa przy końcu tury. Po wszystkich turach osoba z potwierdzonym miejscem na uruchomionym kierunku, PESEL i zaakceptowanym zdjęciem może złożyć ślubowanie. Scenariusz zgłasza stan na podstawie wyniku tych samych warunków. | `candidate_decision`, `move_clock`, `take_oath`, `demo.run_scenario` |
| F15 | MUST | Minima domyślnie wynoszą 20/10/10. Po osiągnięciu minimum kandydat z potwierdzonym miejscem widzi informację o planowanym starcie, a od drugiej tury I/II stopnia widzi ryzyko przy zbyt małym zainteresowaniu. Rozstrzygnięcie następuje na koniec naboru. | `offer_data`, `move_clock`, `finalize` |
| F16 | MUST | Przy ryzyku kandydat otrzymuje informację i może dodać alternatywne zgłoszenie w otwartej turze, zachowując dotychczasowe. | karta zgłoszenia, katalog, powiadomienie |
| F17 | MUST | Powiadomienia obejmują złożenie, weryfikację, publikację, wygaśnięcie, zagrożenie i koniec naboru; użytkownik oznacza własne wiadomości jako przeczytane. | `Notification`, `notify` |
| F18 | MUST | Audyt zapisuje operacje; korekta opublikowanego wyniku wymaga przyczyny i nowej wersji, a poprzedni wynik pozostaje odczytywalny. | `AuditEvent`, triggery, `publish`, `history` |
| F19 | SHOULD | Komisja eksportuje potwierdzone przyjęcia do CSV; eksport ma ograniczony zestaw danych i zabezpiecza komórki przed wykonaniem formuły. | `export`, `csv_safe` |
| F20 | MUST | Ogólna zakładka progów dzieli wyniki według stopnia, trybu i tury; pokazuje „-” przed publikacją, próg punktów/średniej albo kolejność PG, a po finalnym anulowaniu „nie uruchomiono”. | `thresholds`, `page_thresholds` |

Wymagania F01–F20 opisują funkcje wersji 1.0. Testy w `admissions/tests.py` i `tools/e2e_smoke.py` sprawdzają reguły, role i przebieg naboru.

## 10 wymagań niefunkcjonalnych

| ID | MoSCoW | Warunek odbioru | Stan w wersji 1.0 |
|---|---|---|---|
| N01 | MUST | Python i obiektowy podział GUI/API/przypadków użycia/reguł/persystencji; strategie I/II/PG mają wspólny interfejs i niezależne testy. | Zaimplementowano |
| N02 | MUST | PostgreSQL egzekwuje klucze, unikalność, zakresy i zgodność relacji; krytyczne publikacje są atomowe i odporne na równoległe żądania. | Testy SQL i współbieżności |
| N03 | MUST | Hasła haszowane, sesje wygasają i są odwoływane, pliki prywatne, uprawnienia w API. PostgreSQL dostępny tylko na serwerze, klienci LAN łączą się przez HTTPS z walidacją certyfikatu. | Implementacja i testy TLS/autoryzacji |
| N04 | MUST | Ta sama wersja danych i reguł odtwarza ten sam wynik z dokładnością Decimal; publikacje nie są nadpisywane. | Testy punktacji, historii i triggerów |
| N05 | MUST | Pakiet Windows x64 działa po rozpakowaniu bez globalnego Pythona/PostgreSQL; ekran startowy wybiera lokalnie/serwer/klient. Klient importuje plik połączenia i nie tworzy bazy. | Test uruchomienia i importu profilu |
| N06 | SHOULD | Interfejs polski, spójna paleta PK/wydziałów, czytelne stany i błędy, obsługa klawiatury; czytelność przy 1280×800 i większej rozdzielczości. | Test widoków Qt i kontrola zrzutów |
| N07 | SHOULD | Świeży zestaw demonstracyjny i 58 ofert; jeden lokalny klient wykonuje 5 żądań rozgrzewki oraz 30 mierzonych GET /api/catalog. P95 nearest-rank ≤2000 ms, z zapisaniem wszystkich czasów, liczby zgłoszeń, protokołu i sprzętu. Pomiar obejmuje żądanie oraz JSON, bez rysowania GUI. | Automatyczny pomiar w tools/e2e_smoke.py; wynik dla każdego wydania |
| N08 | MUST | Żądania API nie blokują GUI. Serwer obsługuje równoległych klientów, jest źródłem czasu naboru i waliduje termin zapisu. Klient sprawdza zmiany co 5 s, zachowuje filtry i sygnalizuje zmiany podczas edycji. Ponowienie utworzenia/publikacji nie duplikuje danych. | Test 12 klientów HTTPS na połączeniu lokalnym |
| N09 | MUST | Kopia obejmuje bazę i dokumenty; odtworzenie do nowej bazy sprawdza sumy i liczebności, cel ≤30 min dla zestawu demonstracyjnego. | Skrypt oraz test kopii/odtworzenia |
| N10 | MUST | Model ma analizę zależności i normalizacji do 6NF, jawne uzasadnienie fizycznych odstępstw, odtwarzalne pomiary przed/po oraz śledzenie wymagań w dokumentacji technicznej. | Model wszystkich tabel, test bezstratności, fizyczny rozkład kontaktu i eksperymenty indeksu, SELECT oraz denormalizacji |

## Granice i ustalenia techniczne

W projekcie rekrutujemy na I stopień, II stopień i studia podyplomowe. Wpłaty, uruchomienie ofert, aktywacja kont i ślubowanie mają przebieg demonstracyjny. Aplikacja korzysta z publicznej usługi lokalizacji adresów Geoportalu na żądanie kandydata. Linki do projektów GitHub służą komisji do oceny portfolio. Dostarczony informator wyznacza nazwy kierunków i zawodów, a reguły WR i minima są ustaleniami zespołu.

Dokumentacja obejmuje proces, wymagania i przypadki użycia, architekturę, model obiektowy i bazodanowy, transakcje, pomiary i odtwarzanie. Wspólne identyfikatory wiążą te opisy z implementacją i testami.

## Jawna zmiana ustaleń w wersji 0.2

Rozszerzono istniejące identyfikatory o tryb klient–serwer, premie stopniowane, zdjęcie, ślubowanie, operacje zbiorcze i archiwum naborów. Wersja reguł 2027.2 zachowuje historyczne publikacje 2027.1. Ślubowanie i legitymacja mają charakter demonstracyjny. Katalog osiągnięć opisuje reguły aplikacji.

## Zmiany w wersji 0.3

Po testach eksploracyjnych rozszerzono F03 o portal informacyjny przed logowaniem. „Odkryj PK” i „Życie na PK” pokazują ofertę oraz oficjalne materiały o uczelni. F05, F07–F09 i F14 uwzględniają profil, współdzieloną decyzję o zdjęciu oraz jednoznaczną kontrolę dowodu wpłaty. Dane semestralne i scenariusze są demonstracyjne. Uzasadnienia decyzji zawierają [notatki techniczne](architecture/NOTATKI-TECHNICZNE.md).

## Zmiany w wersji 0.4

Pulpit kandydata pokazuje terminy, informacje o akademikach i materiały studenckie. Po osiągnięciu minimum potwierdzeń udostępnia plan zajęć lub stronę dla studentów, aktywację konta, Deltę i zaproszenie na Adapciaka. Po zakończeniu naboru system wysyła powiadomienia wewnętrzne (F12, F15, F17).

„Akademiki” umożliwiają złożenie, zmianę i wycofanie wniosku w edycji z aktywnym zgłoszeniem na I lub II stopień. Odbiór sprawdza przydział po uruchomieniu kierunku, granicę 1800 miejsc, kolejność według odległości i pierwszeństwo wyboru domu według punktacji. W widoku pracowników są liczby i promień najbliższego przydziału. Warunki sprawdzają testy `admissions/test_housing.py` (rozszerzenie F12, F14 i F17).

## Zmiany w wersji 0.5

Profil ma oddzielny, opcjonalny adres do powiadomień, akcje przy każdym dokumencie oraz usuwanie pojedynczych wyników (F05, F07, F17). Wysyłka SMTP używa osobnej kolejki, gdy administrator skonfiguruje pocztę. W menu widać stan nieodczytanych powiadomień. Po ślubowaniu podgląd legitymacji ma półroczną ważność od 1 października (F14). Akademiki mają lokalne podkłady mapowe, a Pulpit karuzelę zdjęć i odnośniki do mediów PK (F12, N06).

## Zmiany w wersji 0.7.0

N07 zmieniono decyzją zespołu z 17.11.2026 na powtarzalny pomiar lokalnego katalogu opisany w tabeli. Poprzedni cel 50 równoczesnych sesji i 100 tys. zgłoszeń nie jest kryterium odbioru tej wersji. Pomiary SQL nadal używają 100 tys. rekordów, a test współbieżności HTTPS jest niezależnym sprawdzeniem.

N10 uzupełnia model logiczny 6NF dla wszystkich tabel, dowód rozkładów i pomiar denormalizacji wraz z ceną utrzymania. ContactAnchor oraz trzy relacje faktów zastępują fizyczną tabelę CandidateContact; widok zachowuje kontrakt aplikacji. Pełna baza fizyczna celowo zawiera wieloatrybutowe relacje operacyjne, obrazy historyczne i projekcje odczytu.

Dokumenty: database/NORMALIZACJA.md, database/POSTGRESQL-MECHANIZMY.md, database/MODELE.md oraz architecture/DECYZJE-ARCHITEKTURY.md.

## Zmiany w wersji 0.8.0

F03 obejmuje „Poznaj wykładowców”, dostępne dla gościa i wszystkich ról: wybór jednego z ośmiu wydziałów, symbole i kolory wydziałów, mapa sylwetek, animowane wyróżnienie wybranej osoby, przykładowe zajęcia i kierunek, zainteresowania, dorobek i wiadomość do kandydata. Publiczne źródło RAD-on ma odnośnik, a sylwetki mają jawnie fikcyjne dane.

W 0.8.1 każdy wydział ma 2 lub 3 sylwetki (18 łącznie). Przy 1280×800 selektory wydziałów mieszczą się w jednym rzędzie, a po zmianie osoby przewinięcie do góry odsłania cały profil. F07 obejmuje komunikat „Podpięto z profilu” i równe wymiary akcji przy plikach. Karta akademików pokazuje liczbę budynków i miejsc z danych edycji.

F07 doprecyzowuje widoczność plików w szkicu: dokumenty z profilu można podejrzeć przed złożeniem, a przelew dodać bezpośrednio przy jego wierszu. Brak samego przelewu nie jest opisywany jako brak świadectwa. Test Qt przechodzi dodanie, zastąpienie, podgląd danych i złożenie zgłoszenia oraz potwierdza zachowanie wersji.
