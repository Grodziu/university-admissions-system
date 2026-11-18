# Źródła i składniki zewnętrzne

Wersja 0.2: własne banery i kolorowy pasek są rysowane w Qt, inspirowane paletą dostarczonego informatora; nie kopiują jego fotografii. Fikcyjne zdjęcie demonstracyjne jest neutralną sylwetką wygenerowaną w kodzie testowym. HTTPS korzysta z Cheroot (BSD) i cryptography (Apache-2.0/BSD, licencje w pakiecie).

- Nazwy I stopnia i mapowanie zawodów: dostarczony `informator_2027-8-1.pdf`, tabela na stronach 5–7.
- Nazwy II stopnia i tryby: [oferta i miejsca PK](https://rekrutacja.pk.edu.pl/liczba-miejsc-na-pierwszym-roku-stacjonarnych-i-niestacjonarnych-studiow-i-i-ii-stopnia/).
- Nazwy podyplomowych: [oferta PK](https://pk.edu.pl/kandydat/studia-podyplomowe/studia-podyplomowe-oferta/). WIiM ma jawnie oznaczony kierunek ilustracyjny, bez przypisywania go oficjalnej ofercie.
- Sygnet PK i paleta: [system identyfikacji wizualnej PK](https://pk.edu.pl/wspolpraca/marka-i-promocja/system-identyfikacji-wizualnej/). Plik źródłowy: `https://pk.edu.pl/wp-content/uploads/2026/09/PK_SYGNET_RGB.webp`. Zmiana formatu do PNG/ICO bez zmiany znaku. Własne liniowe ikony interfejsu powstają w kodzie Qt.
- PostgreSQL 17.12 x64: [EDB binaries](https://www.enterprisedb.com/download-postgresql-binaries), [PostgreSQL License](https://www.postgresql.org/about/licence/). Pakiet zawiera również biblioteki dostarczone przez dystrybutora PostgreSQL.
- Python: PSF License. Django i Django REST Framework: BSD. Psycopg: LGPL. Qt/PySide6: LGPLv3/GPLv3 lub licencja komercyjna, w projekcie wykorzystanie otwartych bibliotek dynamicznych. PyInstaller: GPL z wyjątkiem dotyczącym tworzonych pakietów. Pozostałe biblioteki mają własne dołączone licencje.
- Źródła Qt/PySide6 i informacje o licencjach: [Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html), [repozytorium PySide](https://code.qt.io/cgit/pyside/pyside-setup.git/). Pakiet nie blokuje podmiany dołączonych bibliotek dynamicznych. Font Segoe UI pochodzi z Windows i nie jest kopiowany do paczki.

Wersje bezpośrednich zależności zapisano w `requirements.txt`; `requirements-lock.txt` zawiera komplet środowiska budowania. Kopie dostępnych plików licencji bibliotek są dołączane przez skrypt pakujący do folderu `licenses`. Projekt akademicki nie jest oficjalnym produktem ani portalem rekrutacji PK.

## Ilustracje katalogu i kampusu

| Plik | Autor i licencja | Źródło |
|---|---|---|
| `assets/kampus-pk.jpg` | Politechnika Krakowska, CC0 1.0 | [Budynek siedziby Politechniki Krakowskiej](https://commons.wikimedia.org/wiki/File:Budynek_siedziby_Politechniki_Krakowskiej.jpg) |
| `assets/makieta.jpg` | THOR, [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) | [Architectural Model](https://commons.wikimedia.org/wiki/File:Architectural_Model_(4240901895).jpg) |
| `assets/laboratorium.jpg` | Alexander Bogatyrev, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | [Work in process](https://commons.wikimedia.org/wiki/File:Work_in_process.jpg) |
| `assets/pracownia-komputerowa.jpg` | Mike1024, domena publiczna | [Computer lab at Warwick](https://commons.wikimedia.org/wiki/File:Computer_lab_showing_desktop_PCs_warwick.jpg) |
| `assets/elektronika.jpg` | Laserlicht, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | [Raspberry Pi 4 Model B](https://commons.wikimedia.org/wiki/File:Raspberry_Pi_4_Model_B_-_Side.jpg) |
| `assets/most.jpg` | Ewa Dryjańska, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) | [Most Świętokrzyski](https://commons.wikimedia.org/wiki/File:Most_Swietokrzyski.JPG) |
| `assets/materialy.jpg` | Michelshock, domena publiczna | [Pearlite](https://commons.wikimedia.org/wiki/File:Pearlite.jpg) |
| `assets/energia.jpg` | Andrzej Dworaczek, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | [Wind Power Plant](https://commons.wikimedia.org/wiki/File:Wind_Power_Plant.jpg) |
| `assets/robotyka.jpg` | Nenad Stojković (Shixart1985), [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) | [Robot arm works on a small component](https://commons.wikimedia.org/wiki/File:Robot_arm_works_on_a_small_component_in_a_lab_setting.jpg) |

Zdjęcia tematyczne są ilustracjami wydziałów. Interfejs kadruje je i nakłada gradient, a pliki zachowują dotychczasowe licencje. Zdjęcie kampusu przedstawia siedzibę PK.

Mapy akademików są rysowane w Qt na podstawie współrzędnych placówek i kampusu. Opisy i adresy pochodzą ze stron [Osiedla Studenckiego](https://akademiki.pk.edu.pl/) i [Politechniki Krakowskiej](https://pk.edu.pl/politechnika/o-uczelni/nasze-kampusy/osiedle-studenckie/). Adres budynku kandydata lokalizuje [usługa UUG Geoportalu](https://www.geoportal.gov.pl/wp-media/2023/10/PodstawoweUslugiDanychPrzestrzennychDlaSystemowInformatycznychPanstw-ver.-1.12.pdf).

- Karuzela używa licencjonowanych zdjęć kampusu, panoramy Krakowa, stanowiska robotycznego i Zakrzówka. Dostarczony baner kampanii jest opcjonalnym zasobem lokalnym poza dystrybucją.
- Geometria osiedla `assets/maps/czyzyny-osm.json` pochodzi od © OpenStreetMap contributors. Obejmuje uproszczony wycinek danych w granicach 19.9929, 50.0828, 20.0012, 50.0885. Plik danych jest udostępniany na ODbL 1.0. [Warunki OpenStreetMap](https://www.openstreetmap.org/copyright) · [Wycinek danych](https://api.openstreetmap.org/api/0.6/map?bbox=19.9929,50.0828,20.0012,50.0885).
- `assets/maps/krakow-osm.json` zawiera uproszczone drogi, rzeki, akweny i tereny zielone wokół Krakowa. Dane pochodzą z wyciągu Małopolski od Geofabrik pobranego 17 listopada 2026 r. i są udostępniane na ODbL 1.0. [Wyciąg Małopolski](https://download.geofabrik.de/europe/poland/malopolskie.html) · [© OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
- `assets/maps/region-natural-earth.json` zawiera regionalne drogi i rzeki w skali 1:10 mln. Granice w `assets/maps/granice-natural-earth.json` pochodzą z Natural Earth 1:50 mln. Oba pliki pochodzą z domeny publicznej. [Wektory Natural Earth](https://www.naturalearthdata.com/downloads/10m-physical-vectors/) · [Warunki](https://www.naturalearthdata.com/about/terms-of-use/).
- Oznaczenia Facebooka, Instagrama, Spotify i YouTube pochodzą z zestawu Simple Icons. [Repozytorium i licencja](https://github.com/simple-icons/simple-icons).

## Zdjęcia Krakowa

Fotografie w `assets/krakow/` pochodzą z Wikimedia Commons. Zmniejszono rozdzielczość plików i dobrano kadrowanie do kart. Autorzy, strony zdjęć i licencje są w `assets/krakow/credits.json` i pod każdym zdjęciem w zakładce „Poznaj Kraków”. Panoramę w karuzeli sfotografował Andrzej Otrębski. [Zakole Wisły](https://commons.wikimedia.org/wiki/File:Krakow_zakole_Wisly_panorama.jpg) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
