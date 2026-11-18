# Rekrutacja PK — wersja 1.0

Desktopowa aplikacja Piotra Grodnego i Marcina Gurdziela. Rok akademicki 2026/2027, semestr zimowy. Python, PySide6, Django REST Framework i PostgreSQL.

## Uruchomienie pakietu Windows

1. Rozpakuj cały `RekrutacjaPK-Windows-x64.zip` do zapisywalnego folderu na Windows x64.
2. Uruchom `RekrutacjaPK.exe` albo `Uruchom.bat` i wybierz sposób pracy. „Na tym komputerze” uruchamia samodzielną demonstrację; „Serwer dla zespołu” udostępnia wspólny nabór; „Połącz z serwerem” importuje plik połączenia od administratora. Nie trzeba instalować Pythona ani PostgreSQL.
3. Na ekranie logowania wybierz z listy konto: kandydatka, komisja lub administrator. Hasło jest generowane dla tej kopii i uzupełnia się automatycznie.

Do przekazania programu wyślij ZIP. W trybie klienta dane pozostają na wybranym serwerze. Osobna baza powstaje tylko po wybraniu pracy lokalnej lub uruchomienia własnego serwera. Aby przenieść aktualne dane, użyj kopii z panelu administratora. Kopiowanie żywego katalogu PostgreSQL podczas pracy programu nie jest kopią bezpieczeństwa.

**Zalecany wariant prezentacji: jeden laptop jako serwer, pozostałe w tej samej sieci Wi-Fi / LAN.** W trybie serwera API obsługuje HTTPS, PostgreSQL nadal nasłuchuje tylko na `127.0.0.1`. Instrukcja połączenia, porównanie kontenerów i Internetu: [KLIENT-SERWER.md](architecture/KLIENT-SERWER.md).

Aktualizacja ze starszego wydania. Rozpakuj tę wersję do osobnego folderu. Dane możesz przenieść przez odtworzenie kopii z panelu administratora. Pierwszy start zastosuje migracje. Ślubowanie zachowuje historyczną wersję zdjęcia. Każda instalacja ma własny katalog `runtime`.

Wersja 0.5.1 naprawia start lokalny, gdy port 58421 jest portem PostgreSQL. Okno logowania łączy się z portem zwróconym przez uruchomiony serwer API.

Wersja 0.6.1 zapisuje adres i współrzędne razem. Gdy Geoportal rozpozna budynek pod innym kodem pocztowym, kandydat może zatwierdzić sugerowany kod. Banery i karuzela mają ustalony układ od pierwszej klatki przejścia.

Wersja 0.6.2 dodaje instrukcję ślubowania do powiadomienia „Witaj na Politechnice”. Przycisk „Wstrzymaj” pojawia się razem z karuzelą na Pulpicie.

„Poznaj wykładowców” obejmuje osiem wydziałów, 18 fikcyjnych profili, animowane sylwetki i mapy specjalizacji. W 0.8.1 selektory wydziałów są w jednym rzędzie, a przewijanie po wyborze osoby odsłania cały nagłówek profilu. Publiczne źródło RAD-on jest dostępne z odnośnika.

Dokumenty z profilu są widoczne już w szkicu zgłoszenia. Przy każdym wymaganym pliku można dodać albo zastąpić załącznik; potwierdzenie przelewu należy do konkretnego zgłoszenia. Komunikat o brakach wymienia wyłącznie brakujące dokumenty. Złożenie nadal utrwala wersje plików, a późniejsza podmiana w profilu nie przepisuje historii.

## Co można już przejść

- Gość może otworzyć katalog, opisy kierunków, sylabusy, informator, kampusy, koła i informacje o świadczeniach przed zalogowaniem.
- Kandydat podaje przy rejestracji PESEL, telefon i adres zamieszkania. W „Moim profilu” zarządza jednym zdjęciem, świadectwem, dyplomem, portfolio, olimpiadą i dyplomem technika. Zgłoszenie ustala wersje plików w chwili złożenia. Potwierdzenie wpłaty należy do konkretnego zgłoszenia.
- Komisja sprawdza dokumenty i kwotę przelewu, zwraca do uzupełnienia albo odrzuca z uzasadnieniem. Zatwierdzanie zbiorcze pokazuje kandydatów i powody pominięcia. Wyniki mają jedną pierwszą publikację i oddzielną ścieżkę korekty.
- Komisja i administrator tworzą oferty przed pierwszą turą danego stopnia. W szczegółach oferty wybierają limit, minimum, opłatę, czesne dla trybów odpłatnych, rozszerzenia, kwalifikacje i wymagania portfolio. Ranking można przeszukać według kierunku, wydziału, stopnia i trybu.
- Pulpit pokazuje termin naboru, stan wniosku o akademik, karuzelę zdjęć i materiały PK. Podcast można otworzyć w Spotify lub YouTube. Ikony Facebooka i Instagrama otwierają profile PK, a kafelek radia prowadzi do informacji o stacji.
- „Poznaj Kraków” jest dostępne w panelu kandydata i w trybie gościa. Zawiera zdjęcia, propozycje spacerów oraz odnośniki do muzeów, miejskiego przewodnika i mapy.
- Po osiągnięciu minimum potwierdzonych miejsc kandydat widzi instrukcje aktywacji konta PK, Deltę, informacje o planie zajęć i Adapciaku. Po uruchomieniu oferty powiadomienie trafia do aplikacji. Instrukcje prowadzą do usług i stron uczelni.
- Administrator prowadzi nabór demo etapami, przygotowuje pustą edycję do ustawiania katalogu albo dodaje do niej kandydatów z różnymi stanami. Może utworzyć kopię bazy, zdjęć i dokumentów.
- Zarejestrowany kandydat może zapisać dodatkowy adres e-mail do powiadomień. Czerwona kropka w menu informuje o nieodczytanych pozycjach. Podgląd legitymacji po ślubowaniu ma ważność od 1 października roku rozpoczęcia edycji do 31 marca włącznie.

### Włączanie poczty

Na komputerze serwera ustaw zmienne środowiskowe `PK_SMTP_HOST` i `PK_SMTP_FROM` oraz uruchom program z tego środowiska. Serwer używa domyślnie STARTTLS na porcie 587. Inny port ustaw w `PK_SMTP_PORT`. Dla SMTP z szyfrowaniem od początku wybierz `PK_SMTP_SECURITY=ssl` (domyślnie 465). Login i hasło podaj w `PK_SMTP_USER` oraz `PK_SMTP_PASSWORD`, jeżeli serwer SMTP wymaga logowania.

W „Moim profilu” kandydat wpisuje adres powiadomień i zapisuje profil. Nowa wiadomość w aplikacji trafia do kolejki poczty, jeśli serwer ma włączony SMTP i kandydat podał adres. E-mail zawiera tytuł zdarzenia i odsyła po szczegóły do aplikacji. Zmiana preferencji anuluje oczekującą wysyłkę na poprzedni adres. Odtworzenie kopii bazy anuluje przeniesioną kolejkę wysyłki.

### Katalog studiów

Katalog: 17 kierunków I stopnia (w tym jeden międzywydziałowy), 16 kierunków II stopnia i 8 podyplomowych, łącznie 58 ofert po uwzględnieniu trybu. Na wydziale najwyżej dwa zwykłe kierunki na stopień. „Analiza danych i uczenie maszynowe” na WIiM jest jawnie oznaczoną propozycją projektową; pozostałe nazwy oparto na informatorze i stronach PK. Katalog, limity i harmonogram stanowią demonstracyjny nabór.

„Poznaj kierunek” pokazuje wspólny opis kierunku i stopnia. Przełącznik trybu zmienia dostępność, terminy i czesne. Podane kwoty semestralne są przykładowe. Opisy mają odsyłacze do [sylabusów PK](https://sylabus.pk.edu.pl/) oraz [informatora](https://pk.edu.pl/wp-content/uploads/informator_2027-8-1.pdf).

## Przyjęte reguły

I stopień: `WR = min(1000, 2*M + 6*P1 + 2*P2 + D)`. Z dopuszczonych wyników wybieramy najkorzystniejszą parę, P1 jest lepszym wynikiem; P2 jest drugim wynikiem albo zerem. Premia D wynosi 0, 10, 20, 30, 40 albo 50 po weryfikacji osiągnięcia według katalogu projektu w `admissions/policies.py`. Katalog jest widoczny komisji; nie jest oficjalnym wykazem PK. Wyróżnione portfolio podnosi P2 do 100 po uporządkowaniu podstawowych wyników. Ocena portfolio nie zmienia rankingów II stopnia ani podyplomowych.

II stopień: wyłącznie średnia I stopnia, skala 2–5, dwa miejsca po przecinku. Podyplomowe: dowolny dyplom co najmniej I stopnia i czas kompletnego zgłoszenia; identyczne znaczniki czasu porządkuje stabilne ID. Po zwrocie niekompletnego zgłoszenia do poprawy kolejność ustala czas ponownego złożenia. Różna szybkość pracy komisji nie zmienia kolejności.

I stopień ma 3 tury po 20 dni, II stopień i podyplomowe po 2 tury po 30 dni. Ostatnie 5 dni każdej tury służą weryfikacji, publikacji i potwierdzeniu. Nabór demonstracyjny trwa 1 czerwca–31 lipca 2027. Daty nie są rzeczywistym harmonogramem PK. Minima: 20/10/10; planowane limity: 30/20/15. W I i II stopniu grupa remisowa na granicy zostaje przyjęta w całości. Ostrzeżenie o nieuruchomieniu pojawia się od drugiej tury, a rozstrzygnięcie na koniec wspólnego okresu opiera się na potwierdzonych miejscach.

### Akademiki

Kandydat z aktywnym złożonym zgłoszeniem na I lub II stopień może wskazać jeden preferowany dom na mapie lub liście i zmienić wybór do końca naboru. Mapa pokazuje budynki, ulice i tereny zielone. Podkłady map osiedla i komisji działają offline. W profilu kandydat zapisuje polski adres i klika „Zapisz i ustal położenie adresu”. Geoportal rozpoznaje budynek, a serwer oblicza odległość w linii prostej do kampusu przy ul. Warszawskiej. Numer lokalu pozostaje w profilu. Wniosek zapamiętuje odległość przy zapisie i można ją zaktualizować przez ponowny zapis preferencji. Konta demo mają gotowe położenia do prezentacji offline.

Po ostatnich turach zakwaterowanie obejmuje osoby z potwierdzonym miejscem na uruchomionych studiach. Gdy chętnych jest więcej niż 1800 miejsc, pierwszeństwo mają osoby mieszkające dalej. Domy przydzielamy według wyniku rekrutacji między osobami, które dostały miejsce. Średnią z II stopnia przeliczamy przez mnożnik 200 na skalę z maksimum 1000. Przy braku wolnego miejsca w preferowanym domu przydzielamy dostępne miejsce w innym. Komisja widzi zbiorcze liczby i okrąg o promieniu najmniejszej odległości wśród osób z przydziałem. Limit i podział miejsc na domy są danymi prezentacji.

W widoku statystyk skala mapy dopasowuje się do promienia i rozmiaru okna. Odległość od kampusu zachowuje skalę we wszystkich kierunkach. Podkład wektorowy zmienia szczegółowość wraz z zasięgiem.

Każda oferta ma niezależne zgłoszenie i opłatę. Kwota początkowa to 85 zł. Nie wykonuj prawdziwego przelewu — pliki w `runtime/demo-dokumenty` pozwalają przećwiczyć weryfikację. Zasady punktacji i przyjmowania są ustaleniami projektu, nie wiernym odwzorowaniem regulaminu PK.

## Krótki scenariusz prezentacji

1. Komisja → „Weryfikacja zgłoszeń” → otwórz zgłoszenie Anny Kowalskiej. Sprawdź dokumenty i zdjęcie z profilu, zaznacz zgodność kwoty i zatwierdź zgłoszenie. Zobacz aktualizację w „Rankingu na żywo”.
2. Administrator → „Administracja” → „Wykonaj następny etap”. Serwer przechodzi do następnego terminu i wykonuje związane z nim czynności na kontach przykładowych. Przy ręcznym ustawieniu zegara po zamknięciu zapisów użyj „Kierunki i listy” → „Opublikuj gotowe listy…”.
3. Po ogłoszeniu wyników kandydat potwierdza miejsce. Licznik potwierdzonych miejsc rośnie po tej decyzji. Możesz też wybrać „Odtwórz nabór do ślubowania”, aby serwer rozegrał pozostałe etapy na kontach demo.
4. Przed końcem naboru Anna wchodzi w „Akademiki”, wybiera dom na mapie i składa wniosek. Po zakończeniu naboru widzi wynik i instrukcje zakwaterowania. Komisja otwiera zakładkę „Akademiki” z podsumowaniem.
5. Anna → „Moje zgłoszenia” → „Złóż ślubowanie” → podgląd legitymacji. W pustej edycji administrator wybiera „Zaplanuj ofertę przed pierwszą turą”, edytuje warunki w „Kierunki i listy” i wraca do „Administracji”, by dodać kandydatów demo.

Świeża instalacja ma ponad tysiąc zgłoszeń dla 58 wariantów, również przypadek rezerwy, odrzucenia i braku potwierdzenia. Konta do pokazu są na ekranie logowania. Scenariusz automatyczny wymaga edycji z wyłącznie demonstracyjnymi aktywnymi zgłoszeniami.

## Praca nad kodem

Python 3.13 x64. W nowej kopii źródeł:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe start.py
```

Folder `vendor/pgsql` musi zawierać katalogi `bin`, `lib`, `share` z [pakietu binarnego PostgreSQL 17.12 dla Windows x64](https://www.enterprisedb.com/download-postgresql-binaries). Gotowy pakiet Windows zawiera te katalogi. Przy pracy ze źródłami pobierz PostgreSQL od dystrybutora.

W PyCharm wybierz **File → Open** i wskaż cały folder projektu zawierający `start.py`, `desktop` i `admissions`. Ustaw interpreter Python 3.13 z tego projektu, a potem uruchom `start.py` poleceniem **Run**. Interfejs jest w `desktop/`, reguły i API w `admissions/`, a schemat PostgreSQL w `database/`.

```powershell
python start.py --test
python start.py --benchmark
python start.py --benchmark-query
python tools/e2e_smoke.py
python -m pip install pyinstaller==6.22.3
python build_portable.py
```

Pakiet przenośny powstaje w `dist/v1.0/RekrutacjaPK`. Polecenie `python tools/package_source.py` tworzy oddzielny ZIP do GitHuba z kodem, migracjami, dokumentacją i grafikami. Katalog zawierający `runtime` jest kopią z danymi użytkownika. Do GitHuba trafiają źródła, a paczkę Windows można przypiąć osobno do wydania.

Testy Django tworzą oddzielną bazę `test_rekrutacja`, test HTTP odrębną instancję w `tmp/e2e-*`. Benchmark używa tabel tymczasowych. Żaden z nich nie wymaga danych osobowych.
Gotowy pakiet można sprawdzić poleceniem `python tools/e2e_smoke.py --https --executable dist/v1.0/RekrutacjaPK/RekrutacjaPK.exe --capture-ui`. Test zapisuje wyniki i zrzuty w `tmp/`. Test `python tools/launch_smoke.py` odtwarza kolizję portów i sprawdza uruchomienie okna logowania z przycisku „Na tym komputerze”.

Kopię można zapisać w „Administracja” → „Utwórz kopię bazy i dokumentów”. Polecenie odtworzenia uruchom po zamknięciu okna programu.

```powershell
.\RekrutacjaPK.exe --restore "C:\sciezka\rekrutacja-kopia.zip"
# ze źródeł:
python start.py --restore "C:\sciezka\rekrutacja-kopia.zip"
```

Odtwarzanie tworzy nową bazę, sprawdza SHA-256 plików i liczby rekordów, następnie przełącza lokalny profil. Poprzednia baza zostaje zachowana. Nie odtwarzaj kopii z nieznanego źródła: archiwum zawiera kod obiektów bazy PostgreSQL.

## Podział pracy i stan

- `desktop/`: widoki Qt i klient API; `admissions/domain.py`: obiektowe strategie punktacji; `services.py`: transakcje przypadków użycia; `api.py`: uprawnienia i API.
- `admissions/models.py`, `migrations/`, `database/queries.sql`, `database/benchmark.py`: baza i pomiary. Dokumentację otwiera `database/README.md`.
- `WYMAGANIA.md`: 20 funkcjonalnych i 10 niefunkcjonalnych z MoSCoW, kryteriami i śledzeniem. Aktualizuje starszą koncepcję zgodnie z późniejszymi decyzjami zespołu.
- `architecture/ARCHITEKTURA.md` opisuje architekturę uczelni, wariant E2E/SaaS i strukturę dokumentacji. Wspólna instancja jednej uczelni działa przez HTTPS.
- [Notatki techniczne](architecture/NOTATKI-TECHNICZNE.md) opisują diagramy, podział klient–serwer i uzasadnienia wybranych decyzji.

Model logiczny 6NF, fizyczne fakty kontaktowe, porównanie architektur, modele ER/UML i trzy powtarzalne eksperymenty opisują `database/NORMALIZACJA.md` oraz `architecture/DECYZJE-ARCHITEKTURY.md`.

## Wydanie 0.7.0

Migracja 0011 rozdziela telefon, portfolio i e-mail na niezależne fakty; profil zachowuje dotychczasową obsługę. Model ER i UML ma pełne atrybuty, a eksport modelu sprawdza bezstratną rekonstrukcję wszystkich tabel. Dodano porównanie architektur całej uczelni i eksperyment denormalizacji z pomiarem kosztu zapisu.

Instrukcje: [użytkownik](architecture/INSTRUKCJA-UZYTKOWNIKA.md), [administrator bazy](database/ADMINISTRACJA.md), [modele do narzędzia](database/MODELE.md). Nowe N07 mierzy 30 odczytów katalogu jednym lokalnym klientem.

`python tools/package_source.py --github-dir` tworzy źródłowy ZIP i osobny katalog do publikacji. Eksport zawiera kod, migracje, zdjęcia, mapy, ikony i dokumentację techniczną. Karuzela zawiera zdjęcia kampusu, panoramy Krakowa, stanowiska robotycznego i Zakrzówka. Prywatne materiały, runtime, dokumenty i binaria vendor pozostają poza źródłami.
