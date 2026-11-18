# Architektura uczelni i decyzje projektowe

Przegląd: 17.11.2026, wydanie 0.7.0. Dokument oddziela wdrożony moduł rekrutacji od projektowanej architektury całej uczelni. Decyzje zapisano na podstawie aktualnego kodu i ograniczeń zespołu; nie są pozorowaną historią wcześniejszych zatwierdzeń.

## Cele biznesowe i granice

Cele: przeprowadzenie naboru w terminach, jednakowe i odtwarzalne kwalifikowanie, zachowanie dowodów decyzji, kontrolowany dostęp do danych, obsługa kandydata od wyboru studiów do przyjęcia oraz przekazanie danych do dalszej obsługi studenta.

Cała uczelnia obejmuje: promocję i ofertę, rekrutację, dziekanat i tok studiów, organizację dydaktyki, LMS, bibliotekę i repozytoria, badania i granty, finanse, kadry i płace, akademiki i świadczenia, dostępność, majątek i zamówienia oraz raportowanie zarządcze. Usługi wspólne to tożsamość, uprawnienia, komunikacja, obieg dokumentów, audyt i administracja.

W implementacji działają rekrutacja, profil i dokumenty, katalog, punktacja, publikacja, potwierdzanie, ślubowanie demonstracyjne, akademiki, poczta, treści informacyjne i administracja. Przekazanie przyjętych odbywa się przez kontrolowany eksport CSV. Dziekanat, finanse, LMS, kadry, badania i biblioteka pozostają kontekstem integracji. Odnośnik do zewnętrznej strony nie oznacza integracji danych. Od 0.8.0 działa moduł demonstracyjnych sylwetek prowadzących; import rzeczywistych danych POL-on/RAD-on pozostaje projektem integracji.

## ADR-01. Klasa przechowywania i SZBD

| Klasa | Dopasowanie do danych i reguł | Koszt/ograniczenie | Wniosek |
|---|---|---|---|
| Relacyjna | Klucze, związki, wielotabelowe transakcje, rankingi i wersje | Koszt JOIN i świadomego modelowania | Podstawowy model operacyjny |
| Dokumentowa NoSQL | Elastyczny dokument i odczyt całego agregatu | Związki kandydat–oferta–tura i reguły między nimi nadal trzeba egzekwować | JSONB jako pomocnicza wartość w relacyjnym modelu |
| Klucz–wartość | Szybkie odczyty po identyfikatorze | Brak naturalnego modelu złączeń i kontroli reguł naboru | Potencjalny cache, obecnie zbędny |
| Grafowa | Nawigacja w sieci zależności | Główne operacje to tablice kwalifikacyjne i transakcje, nie przejścia grafowe | Bez uzasadnienia jako główny magazyn |
| Rozproszona baza SQL/NoSQL | Replikacja geograficzna i duża skala | Konsensus, obsługa awarii częściowych, wdrożenie wielowęzłowe | Rozważyć po udowodnieniu potrzeby |
| Blockchain | Wspólny rejestr bez jednego zaufanego operatora | Uczelnia ma operatora i potrzebuje kontroli danych osobowych | Brak potrzeby domenowej |
| Hurtownia | Analizy historyczne i agregacje | Zasilanie i opóźnienia; nie zastępuje źródła transakcji | Docelowy odbiorca zagregowanych danych |

Wybrano PostgreSQL: transakcje, ograniczenia, blokady wierszy, SQL/PL/pgSQL, różne indeksy, JSONB i narzędzia kopii pozwalają przeprowadzić cały proces na jednym silniku. SQLite uprościłby dystrybucję, ale nie odwzorowałby używanych mechanizmów PostgreSQL i wspólnego serwera. Oracle dostarcza dodatkowe techniki fizyczne, lecz zwiększyłby wymagania dystrybucji i administracji. Terminologię indeksów rozstrzyga osobny dokument POSTGRESQL-MECHANIZMY.md.

## ADR-02. Styl architektoniczny

Porównanie dla dwóch wykonawców, jednego modułu operacyjnego, lokalnej demonstracji i możliwej pracy LAN. Skala 1–5: 5 oznacza lepsze dopasowanie; oceny to jawna ocena inżynierska, nie wyniki benchmarku.

| Kryterium | Waga | Monolit modułowy | Mikroserwisy | Pełna architektura zdarzeniowa |
|---|---:|---:|---:|---:|
| Spójność i niezawodność procesu | 25% | 5 | 3 | 3 |
| Prostota uruchomienia i utrzymania | 25% | 5 | 2 | 2 |
| Zmiany i granice domen | 20% | 4 | 5 | 4 |
| Niezależne skalowanie | 15% | 3 | 5 | 5 |
| Koszt wdrożenia i diagnostyki | 15% | 5 | 2 | 2 |
| Wynik ważony | 100% | **4,50** | **3,30** | **3,10** |

Decyzja: modułowy monolit Django/DRF i PostgreSQL, z osobnym klientem PySide6. Operacje kwalifikacji wykonują się w jednej transakcji. Poczta korzysta z utrwalonej kolejki i ponowień, ale to nie czyni całego systemu mikroserwisowym. Nie ma brokera Kafka/RabbitMQ, API Gateway, Sagi ani Kubernetes.

W architekturze całej uczelni granice dziedzin pozostają jawne. Dziekanat, LMS, kadry i finanse mogą być niezależnymi istniejącymi aplikacjami. Integracja powinna odbywać się przez kontrakty i kontrolowany import, bez bezpośredniego zapisu do tabel innych domen. Rekrutacja zachowuje własne dane i publikuje wynik przyjęcia. Wprowadzenie kolejki integracyjnej wymaga idempotencji, obsługi wersji kontraktu i potwierdzenia odbioru. To kierunek projektu, nie deklaracja gotowej implementacji.

## ADR-03. Sposób świadczenia usługi

IaaS opisuje udostępnienie infrastruktury, on-premise jej lokalizację, SaaS sposób dostarczenia aplikacji, a E2E zakres odpowiedzialności dostawcy. Nie są wzajemnie wykluczającymi się stylami architektonicznymi.

| Wariant | Izolacja i odpowiedzialność | Koszt i ryzyko | Decyzja |
|---|---|---|---|
| Dedykowana instancja w uczelni, obsługa E2E | API, baza i pliki jednej uczelni; operator odpowiada za kopię i aktualizację | Więcej instancji do utrzymania; łatwiejsze odtwarzanie jednej uczelni | Wariant wdrożony, zalecany do prezentacji LAN |
| Dedykowana instancja na IaaS | Taka sama izolacja; dostawca infrastruktury nie zastępuje administratora aplikacji | Potrzebne zabezpieczenie hosta, TLS, monitoring i procedury | Projekt wariantu przeniesienia |
| Wspólna aplikacja SaaS, osobna baza i pliki każdej uczelni | Wspólny kod/serwer routuje po zaufanej tożsamości instancji | Wspólna awaria API, pule połączeń, kontrola routingu i aktualizacji | Preferowany docelowy wariant współdzielony |
| Wspólna aplikacja i baza z tenant_id/RLS | Wszystkie klucze, zapytania i pliki muszą uwzględniać uczelnię | Najtrudniejsze selektywne odtwarzanie i ryzyko wycieku między uczelniami | Odrzucono dla obecnej skali |

Wybrano dedykowaną bazę jednej uczelni na instancję. Wspólny wariant SaaS zaprojektowano z osobnymi bazami; wymaga rejestru instancji i routingu po stronie serwera. Klient nie wybiera dowolnej nazwy bazy. Wspólna treść publiczna może być współdzielona niezależnie od danych osobowych. Implementacja nie obsługuje jeszcze wielu uczelni w jednym procesie.

Model wdrożenia pokazuje oba warianty, żeby decyzja nie ograniczała całej uczelni do pojedynczego komputera. Sam dodatek tenant_id do kilku tabel nie stanowiłby kompletnego rozwiązania izolacji.

## ADR-04. Model logiczny i fizyczny

Model logiczny 6NF rozdziela niezależne fakty. Schemat fizyczny jest odwzorowaniem zoptymalizowanym dla transakcji i odczytów Django. Dane kontaktowe rozłożono także fizycznie; widok zachowuje kontrakt aplikacji. Dane historyczne mają wersje, a liczniki są kontrolowaną projekcją.

Wariant „wyłącznie faktowe tabele dla każdego pola na ścieżce zapisu” zwiększyłby liczbę złączeń i wymagał przeniesienia wieloatrybutowych ograniczeń do constraint triggers. Wariant „jedna płaska tabela” wprowadza anomalie. Wybrano pełny model odniesienia z testem bezstratności i jawne fizyczne odstępstwa. Szczegóły zawiera NORMALIZACJA.md.

## ADR-05. Dostępność, trwałość i bezpieczeństwo

Wersja demonstracyjna działa na pojedynczym serwerze: awaria hosta przerywa dostęp. Nie deklarujemy SLA 99,9%, klastra HA ani replikacji jako uruchomionych funkcji. Trwałość opiera się na transakcjach PostgreSQL, walidacji, kopii bazy i dokumentów oraz sprawdzonym odtworzeniu.

Rola pk_owner wykonuje migracje; pk_app ma ograniczone uprawnienia. Surowy audyt, publikacje, ranking, liczniki i tabele kontaktowych faktów są dodatkowo chronione. Wyzwalacze SECURITY DEFINER mają ustalony search_path; hasła bazy pozostają na serwerze. LAN używa HTTPS z weryfikacją prywatnego CA, PostgreSQL słucha tylko na loopback. Obsługiwane minimum TLS wynika z konfiguracji serwera; nie deklarujemy wyłącznego TLS 1.3 ani pełnego szyfrowania wszystkich plików w spoczynku.

Docelowy serwer uczelniany wymaga kopii poza hostem, monitorowania, aktualizacji, testu odtworzenia oraz uzgodnienia RPO/RTO. Replikacja nie zastępuje kopii przy błędzie logicznym.

## Ryzyka, nakłady i koszt decyzji

Poniższe liczby to porównawczy scenariusz planistyczny: 12 miesięcy, roboczogodzina 100 zł, zastępczy koszt przestoju 200 zł/h. Nie są ofertą, zmierzonym SLA ani rzeczywistą stratą uczelni.

| Wariant | Uruchomienie [h] | Utrzymanie [h/mies.] | Infrastruktura [zł/mies.] | Model TCO roczny [zł] |
|---|---:|---:|---:|---:|
| Monolit modułowy | 16 | 3 | 150 | 7 000 |
| Mikroserwisy | 48 | 8 | 350 | 18 600 |
| Architektura zdarzeniowa | 40 | 7 | 300 | 16 000 |

TCO = uruchomienie × 100 + 12 × (utrzymanie × 100 + infrastruktura). Kod już istnieje; tabela porównuje dodatkową obsługę wdrożenia i utrzymania, a nie koszt napisania produktu. Nie wyprowadzamy ROI/NPV z nieistniejących przychodów. Dla lokalnego pokazu koszt używanego laptopa jest zasobem istniejącym.

| Ryzyko w horyzoncie roku | P scenariusza | Skutek | Model straty [zł] | P × strata | Działanie |
|---|---:|---|---:|---:|---|
| Awaria jednego hosta | 0,20 | 8 h przestoju + 4 h odtworzenia pracy administratora | 2 000 | 400 | Kopia poza hostem, kontrola SHA-256, próba odtworzenia |
| Niezgodność wersji klient–API | 0,30 | 4 h diagnostyki + 2 h przestoju | 800 | 240 | Wersja w health, test pakietu i umowa kontraktu |
| Błąd migracji | 0,10 | 6 h naprawy + 4 h przestoju | 1 400 | 140 | Kopia, migracja na kopii, test aktualizacji i powrotu |
| Błąd routingu SaaS | 0,05 | Szacunkowy wpływ incydentu 40 000 zł | 40 000 | 2 000 | Osobne bazy, autoryzacja instancji i testy izolacji przed uruchomieniem |
| Utrata połączenia internetowego | 0,40 | Niedostępne zewnętrzne linki/lokalizacja, 2 h obsługi | 200 | 80 | Lokalne grafiki, dane demonstracyjne i czytelny błąd integracji |

Prawdopodobieństwa i wpływ są założeniami do dyskusji i analizy wrażliwości. Podwojenie stawki pracy podnosi modelowe TCO monolitu do 12 200 zł, mikrousług do 33 000 zł, EDA do 28 400 zł; kolejność wyboru pozostaje taka sama. Współdzielenie API ma sens po wzroście liczby klientów i pomiarze korzyści, nie na podstawie samej popularności stylu.

## Trzy poziomy i trzy perspektywy

- Poziom biznesowy: aktorzy i usługi uczelni, proces przyjęcia i dalszego toku studiów.
- Poziom aplikacji: komponenty domenowe, właściciele danych i kontrakty wymiany.
- Poziom technologiczny: stacja klienta, serwer API, PostgreSQL, magazyn plików, kopie, sieć i poczta.

Pliki PlantUML:
- models/uczelnia-kontekst.puml — cała uczelnia i zależności;
- models/uczelnia-warstwy.puml — trzy poziomy ArchiMate;
- models/rekrutacja-komponenty.puml — komponenty i łączniki wdrożonej aplikacji;
- models/rekrutacja-moduly.puml — pakiety i zależności kodu;
- models/wdrozenie-warianty.puml — alokacja dedykowana oraz projekt SaaS;
- models/rekrutacja-proces.puml — czynności i granice ról;
- models/klasy-regul.puml — rzeczywisty interfejs strategii obliczeń.

Otwórz plik w PlantUML albo wtyczce obsługującej ten format. ArchiMate korzysta ze standardowej biblioteki PlantUML. Rysunki oznaczają elementy projektowane osobnym stereotypem. Nie deklarujemy przeprowadzenia pełnego procesu TOGAF ani certyfikacji modelu.

## Powiązanie z kodem i sprawdzalne wymagania

Client HTTP → admissions.api → services/profiles/offers/housing → domain/policies → modele i PostgreSQL. Pliki obsługuje serwer, powiadomienia mają rekord Notification i opcjonalnie EmailDelivery. portable.py uruchamia bazę, migracje i uprawnienia; backups.py tworzy i odtwarza pakiet bazy oraz dokumentów.

N07 zastąpiono prostym odbiorem: świeża edycja demonstracyjna, 58 ofert, jeden klient lokalny, 5 żądań rozgrzewki i 30 mierzonych GET /api/catalog, p95 nearest-rank ≤ 2000 ms. Pomiar obejmuje HTTP/HTTPS i dekodowanie JSON, bez rysowania GUI. Liczbę zgłoszeń i sprzęt zapisuje test. Cel 50 równoczesnych sesji/100 tys. zgłoszeń wycofano z tego wymagania decyzją zespołu 17.11.2026. Eksperymenty SQL na 100 tys. wierszy pozostają odrębne.

Testy migracji, wszystkich reguł, współbieżności, przebiegu przez klienta, TLS, kopii i odtwarzania są warunkami przyjęcia zmiany. Odbiór w fizycznej sieci dwóch laptopów pozostaje oddzielną czynnością wdrożeniową.
