# Modele do otwarcia w narzędziu

Wszystkie pliki znajdują się w models/. Zawierają strukturę i nazwy pól, bez rekordów kandydatów.

| Plik | Program i sposób użycia |
|---|---|
| model.dbml | dbdiagram.io: nowy diagram, wklej cały tekst DBML; można też użyć lokalnego narzędzia zgodnego z DBML |
| model.mmd | Edytor Mermaid obsługujący erDiagram: wklej tekst. Pełne tabele obejmują także techniczne obiekty Django |
| classes.puml | PlantUML: wklej od @startuml do @enduml; diagram rzeczywistych klas i ich atrybutów |
| model-catalog.json | Katalog maszynowy: typy, NULL, klucze, CHECK, kategoria i FD |
| model-6nf.sql | DDL referencyjnego rozkładu do 6NF. Wykonaj wyłącznie w osobnej bazie demonstracyjnej |

Odświeżenie modeli i weryfikacja rekonstrukcji: python start.py --export-model. Narzędzie obejmuje wszystkie aktualne tabele public, tworzy kotwice i relacje faktów w transakcji wycofywanej po porównaniu. Każda tabela musi mieć pojedynczy klucz główny; dla klucza złożonego eksporter żąda jawnego mapowania, zamiast tworzyć niepoprawny diagram.

Pełny diagram można podzielić na obszary profilu, katalogu, rekrutacji, wyników, akademików i administracji. Katalog JSON i DDL pozostają pełnym źródłem szczegółów. Pliki architektury całej uczelni w architecture/models są odrębną perspektywą od modelu bazy.

Składnię definiują [DBML](https://dbml.dbdiagram.io/docs/) i [PlantUML](https://plantuml.com/class-diagram).
