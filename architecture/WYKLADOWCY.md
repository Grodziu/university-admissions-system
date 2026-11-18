# Poznaj wykładowców

Od wydania 0.8.0 moduł jest częścią natywnej aplikacji PySide6, dostępną w menu gościa, kandydata, komisji i administratora. „Odkryj PK” zawiera dodatkowy przycisk otwierający moduł.

Hierarchia: osiem wydziałów → sylwetki na mapie → wybrany profil. Symbole i kolory korzystają z tych samych ProgrammeMark i definicji wydziałów co katalog kierunków. Od 0.8.1 selektory mieszczą się w jednym rzędzie w oknie aplikacji. Animacja zmienia rozmiar portretu w jego stałych granicach, dzięki czemu profil zachowuje swój układ przy przewijaniu. Mapa specjalizacji pokazuje tematy badań. Profil zawiera przykładowy przedmiot, kierunek, semestr, ćwiczenie, dorobek i wiadomość do kandydata.

## Zakres danych

Osiemnaście osób, przypisania zajęć, wypowiedzi i dorobek są fikcyjne i oznaczone jako demonstracyjne. Każdy wydział ma dwie lub trzy osoby. Ilustracje to autorskie grafiki wektorowe rysowane w Qt, dostępne bez internetu.

admissions/academic_staff.py jest wspólnym, wersjonowanym katalogiem danych informacyjnych. Udostępnia go publiczne, odczytowe GET /api/lecturers; interfejs używa tej samej definicji lokalnej, aby otwarcie modułu nie wymagało pobierania danych. Nie dodano nowych tabel do transakcyjnej bazy rekrutacji ani edytora profili.

Odnośnik prowadzi do publicznego RAD-on. Nie przypisujemy fikcyjnym osobom identyfikatorów prawdziwych naukowców i nie deklarujemy synchronizacji rejestru. Publiczne dane i kanały API opisuje [POL-on](https://polon.nauka.gov.pl/siec-polon/dane-publiczne/) oraz [katalog API RAD-on](https://radon.nauka.gov.pl/pomoc/knowledge-base/katalog-udostepnianych-danych-api/). Import rzeczywistych profili wymagałby oddzielnego mapowania, ustalenia źródła zdjęć i przypisań dydaktycznych oraz weryfikacji danych.

## Kod i weryfikacja

- desktop/lecturers.py: LecturerExplorer, PeopleMap, PersonButton, Portrait i ResearchMap;
- desktop/programme_marks.py: wspólne symbole wydziałów;
- admissions/academic_staff.py: profile i mapowanie wydział–kierunek;
- admissions/api.py i server/urls.py: publiczny odczyt katalogu;
- tools/ui_smoke.py: dostępność w rolach, wybór wszystkich wydziałów i przełączenie profilu;
- admissions/test_evidence_and_staff.py: jawność danych demonstracyjnych, mapowanie programu oraz brak operacji zapisu.

Menu boczne ma przewijany obszar zakładek, dzięki czemu dodatkowy moduł pozostaje dostępny w mniejszych oknach.
