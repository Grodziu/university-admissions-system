# Dokumentacja danych

- [Model i normalizacja](NORMALIZACJA.md): klucze, zależności, przykłady UNF–6NF, DKNF, bezstratność i fizyczne odstępstwa.
- [Modele do narzędzia](MODELE.md): ER w DBML/Mermaid, UML klas, katalog atrybutów i referencyjny DDL 6NF.
- [PostgreSQL i indeksy](POSTGRESQL-MECHANIZMY.md): rzeczywiste możliwości, różnice IOT/bitmap/reverse i próby mechanizmów.
- [Administracja](ADMINISTRACJA.md): role, migracje, kopie, odtworzenie i kontrola integralności.
- [Przykładowe zapytania](queries.sql) i [przykłady normalizacji](normalization_examples.sql).
- [DDL aktualnego schematu](schema.sql).
- benchmark.py, query_rewrite.py i denormalization.py: trzy odrębne eksperymenty, pełne plany i wyniki przed/po.
- normalization_cases.py: sprawdzenie rozkładów na rzeczywistych relacjach.
- index_capabilities.py: bezpieczne próby mechanizmów na tabelach TEMP.

Wyniki są zależne od zbioru, sprzętu i obciążenia. Eksperymenty zapisują konfigurację i wszystkie powtórzenia. Działanie użytkowe oraz architekturę opisują README projektu i architecture/.
