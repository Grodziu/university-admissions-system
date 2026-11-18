"""Editorial programme profiles and official resources for prospective students."""
from admissions.catalog_data import PG_SOURCE, POSTGRADUATE

INFORMATOR_URL = 'https://pk.edu.pl/wp-content/uploads/informator_2027-8-1.pdf'
SYLLABUS_URL = 'https://sylabus.pk.edu.pl/'
FEES_URL = 'https://rekrutacja.pk.edu.pl/oplaty/'
CAMPUS_URL = 'https://pk.edu.pl/politechnika/o-uczelni/nasze-kampusy/'
CAMPUS_MAP = 'https://samorzad.pk.edu.pl/mapa/'
FUTURELAB_URL = 'https://rekrutacja.pk.edu.pl/poradnik/gdzie-pasja-spotyka-przyszlosc-twoja-droga-do-sukcesu-na-politechnice-krakowskiej/'
PK_HOME = 'https://pk.edu.pl/'

# These are editorial examples of work in the field. The linked syllabus lists the
# actual courses for a particular degree, study mode and cohort.
PROGRAMME_STORIES = {
    'Architektura': (
        'Jak zaprojektować dom, który daje światło zimą i cień latem? Na architekturze łączysz rysunek i pracę w pracowni projektowej z konstrukcją, historią miasta i technologią budowania.',
        'Przełóż analizę działki na szkice, makietę i model przestrzenny budynku.',
        'Pracownie architektoniczne, urbanistyka, projektowanie wnętrz i cyfrowe modelowanie budynków.'),
    'Architektura krajobrazu': (
        'Zaprojektuj przestrzeń, w której chce się zatrzymać. Nauczysz się czytać krajobraz, dobierać rośliny do warunków i projektować zieleń, która dobrze znosi upały i zatrzymuje wodę.',
        'Zaproponuj nowy układ ścieżek, nasadzeń i miejsc odpoczynku dla zaniedbanego parku.',
        'Pracownie krajobrazu, rewitalizacja terenów, zarządzanie zielenią miejską.'),
    'Gospodarka przestrzenna': (
        'Gdzie warto zbudować osiedle, a gdzie zachować otwartą przestrzeń? Ten kierunek łączy projektowanie miasta z analizą danych, transportem i ochroną środowiska.',
        'Użyj map i danych przestrzennych, by sprawdzić dostęp do szkół, komunikacji i terenów zielonych.',
        'Planowanie przestrzenne, analizy GIS, samorządy i konsulting urbanistyczny.'),
    'Informatyka': (
        'Masz pomysł na aplikację? Nauczysz się przejść od pierwszego prototypu do programu, z którego mogą korzystać inni. Programowanie łączy się tu z algorytmami, bazami danych i projektowaniem systemów.',
        'Zbuduj i przetestuj usługę, która wyszukuje w zbiorze danych, zapisuje wyniki i udostępnia je użytkownikom.',
        'Tworzenie oprogramowania, inżynieria danych, testowanie i rozwój systemów.'),
    'Matematyka stosowana': (
        'Szukaj reguł, których nie widać na pierwszy rzut oka. Matematyka stosowana łączy modelowanie, statystykę i obliczenia, dzięki którym można przewidywać zdarzenia i porównywać decyzje.',
        'Porównaj modele prognozowania, uwzględniając niepewność wyników i jakość danych.',
        'Analiza danych, modelowanie w technice, optymalizacja i analityka ryzyka.'),
    'Elektrotechnika i automatyka': (
        'Zaprojektuj układ, który trafnie reaguje na odczyty czujników. Ten kierunek łączy obwody elektryczne, pomiary, napędy oraz sterowanie maszynami i procesami.',
        'Dobierz czujniki i zaprogramuj sterownik, aby układ utrzymywał zadaną temperaturę lub prędkość.',
        'Automatyka przemysłowa, elektroenergetyka, projektowanie instalacji i napędów.'),
    'Informatyka w inżynierii komputerowej': (
        'Ulubiony program może działać też poza komputerem. Poznaj mikrokontrolery, komunikację urządzeń i oprogramowanie, które łączy czujniki z systemami przetwarzającymi dane.',
        'Zbuduj prototyp stacji pomiarowej i zaprojektuj bezpieczne przesyłanie odczytów.',
        'Systemy wbudowane, IoT, oprogramowanie sprzętu i integracja urządzeń.'),
    'Infotronika': (
        'Połącz pomiar, elektronikę i przetwarzanie sygnałów w jednym systemie. To kierunek dla osób zainteresowanych tym, jak sprzęt i oprogramowanie współpracują w rozwiązaniach technicznych.',
        'Zaprojektuj układ monitorowania maszyny i wyodrębnij z sygnału cechy informujące o jej stanie.',
        'Elektronika, diagnostyka, systemy pomiarowe i integracja automatyki.'),
    'Budownictwo': (
        'Sprawdź, co sprawia, że konstrukcja jest bezpieczna i można ją rzeczywiście zbudować. Poznasz pracę z materiałami, obciążeniami, dokumentacją i organizacją robót.',
        'Porównaj warianty konstrukcji, oblicz jej nośność i przygotuj model do współpracy z innymi branżami.',
        'Biura projektowe, wykonawstwo, nadzór inwestycyjny i modelowanie BIM.'),
    'Transport i logistyka': (
        'Jak przewieźć ludzi i towary sprawniej, przy mniejszym zużyciu zasobów? Zajmiesz się planowaniem przewozów, organizacją ruchu i przepływem towarów między dostawcami i odbiorcami.',
        'Porównaj trasy, rozkłady lub układy magazynu na podstawie kosztów i czasu.',
        'Operatorzy transportu, logistyka, centra dystrybucyjne i planowanie mobilności.'),
    'Fizyka techniczna': (
        'Zacznij od pytania o światło, energię lub właściwości materiału i zbuduj pomiar, który pomoże Ci na nie odpowiedzieć. Połącz model fizyczny z pracą laboratoryjną i analizą danych.',
        'Zaprojektuj doświadczenie i przeanalizuj, które źródło błędu najbardziej wpływa na pomiar.',
        'Laboratoria pomiarowe, optyka i fotonika, modelowanie techniczne i badania.'),
    'Inżynieria materiałowa': (
        'Lżejszy element może mieć taką samą wytrzymałość, jeśli dobrze dobierzesz materiał. Zbadasz, jak struktura metali, polimerów i kompozytów wpływa na ich zachowanie w pracy.',
        'Zbadaj próbkę, porównaj jej wytrzymałość i zaproponuj materiał odpowiedni do danego obciążenia.',
        'Badanie materiałów, jakość w przemyśle i rozwój nowych technologii wytwarzania.'),
    'Energetyka': (
        'Przekonaj się, ile energii można odzyskać z procesu, który zwykle traci ciepło. Zajmiesz się wytwarzaniem i dystrybucją energii, odnawialnymi źródłami oraz sprawnością instalacji.',
        'Zaproponuj zestaw źródeł ciepła i porównaj zużycie energii w kilku wariantach.',
        'Przedsiębiorstwa energetyczne, efektywność energetyczna, OZE i serwis instalacji.'),
    'Inżynieria środowiska': (
        'Zaprojektuj instalację, która oszczędza wodę i zapewnia ludziom komfort. W tym obszarze spotykają się projektowanie sieci, technologie oczyszczania, wentylacja i gospodarowanie wodą.',
        'Oblicz potrzeby budynku lub osiedla i dobierz sposób odprowadzenia oraz retencji deszczówki.',
        'Przedsiębiorstwa wodociągowe, biura instalacyjne i infrastruktura środowiskowa.'),
    'Biotechnologia przemysłowa': (
        'Poznaj zastosowania procesów biologicznych w wytwarzaniu materiałów i produktów. Nauczysz się oceniać, co decyduje o jakości próbki i jak przenieść proces z laboratorium do produkcji.',
        'Porównaj wyniki pomiarów i zaproponuj sposób monitorowania jakości procesu.',
        'Laboratoria analityczne, kontrola jakości i innowacje w przemyśle.'),
    'Technologia chemiczna': (
        'Od próbki do gotowego produktu prowadzi droga pełna decyzji o surowcach, aparaturze i jakości. Poznasz analizę chemiczną i projektowanie procesów w skali przemysłowej.',
        'Opracuj bilans surowców i porównaj dwa sposoby oczyszczania produktu.',
        'Technologia produkcji, laboratoria, kontrola jakości i rozwój produktów.'),
    'Mechanika i budowa maszyn': (
        'Rozbierz w wyobraźni maszynę na części i zaprojektuj ją od nowa. Na kierunku łączysz mechanikę, CAD, materiały i techniki wytwarzania, by pomysł stał się sprawnym urządzeniem.',
        'Zaprojektuj przekładnię lub uchwyt, a potem oceń, czy da się go wykonać i bezpiecznie używać.',
        'Biura konstrukcyjne, utrzymanie ruchu, motoryzacja i przemysł wytwórczy.'),
    'Informatyka stosowana': (
        'Wykorzystaj programowanie do rozwiązywania problemów technicznych. Połącz analizę danych i symulacje z oprogramowaniem wspierającym projektowanie, pomiary albo pracę maszyn.',
        'Przygotuj prototyp narzędzia, które porównuje wyniki symulacji z pomiarami.',
        'Oprogramowanie inżynierskie, symulacje, przetwarzanie danych z urządzeń.'),
    POSTGRADUATE['WA']: (
        'Przejmij kontrolę nad informacją o budynku od projektu do użytkowania. Poznaj pracę na wspólnym modelu i sposób wymiany danych pomiędzy architekturą, konstrukcją oraz instalacjami.',
        'Skoordynuj modele kilku branż i wykryj kolizje przed rozpoczęciem robót.',
        'Koordynacja BIM, zarządzanie informacją o inwestycji i cyfryzacja projektowania.'),
    POSTGRADUATE['WIiM']: (
        'Przejdź od surowych danych do odpowiedzi na pytanie biznesowe. Ta przykładowa oferta obejmuje analizę danych, dobór modelu i ocenę, czy prognoza nadaje się do użycia.',
        'Przygotuj zbiór danych, porównaj dwa modele i zaprezentuj błędy predykcji.',
        'Analityka, inżynieria danych i wdrażanie modeli do procesów biznesowych.'),
    POSTGRADUATE['WIEiK']: (
        'Poznaj zagadnienia ochrony urządzeń i systemów używanych w obiektach przemysłowych. Oceniaj ryzyko z uwzględnieniem ciągłości pracy, bezpieczeństwa ludzi i współpracy działów.',
        'Przygotuj analizę ryzyka oraz plan reagowania na przykładowe zdarzenie w zakładzie.',
        'Zarządzanie bezpieczeństwem OT, automatyka i utrzymanie infrastruktury.'),
    POSTGRADUATE['WILiT']: (
        'Zrozum, jak układ ulic wpływa na płynność i bezpieczeństwo ruchu. Rozwijaj umiejętność oceny węzłów, planowania organizacji ruchu i interpretacji pomiarów.',
        'Przeanalizuj ruch na skrzyżowaniu i porównaj warianty zmiany organizacji.',
        'Zarządy dróg, projektowanie organizacji ruchu i analiza mobilności.'),
    POSTGRADUATE['WIMiF']: (
        'Połącz znajomość materiałów z oceną jakości połączeń spawanych. Poznaj dokumentację procesu, dobór technologii i rolę nadzoru nad produkcją.',
        'Porównaj technologie łączenia i zaproponuj plan kontroli jakości spoiny.',
        'Nadzór spawalniczy, produkcja konstrukcji i kontrola jakości.'),
    POSTGRADUATE['WIŚiE']: (
        'Rozwijaj umiejętności potrzebne do utrzymywania sieci, od rozpoznawania strat wody po planowanie prac. Zbadaj, jak dane pomiarowe pomagają w codziennej eksploatacji.',
        'Zaproponuj sposób wskazywania odcinków sieci wymagających naprawy.',
        'Eksploatacja sieci, przedsiębiorstwa komunalne i zarządzanie majątkiem technicznym.'),
    POSTGRADUATE['WIiTCh']: (
        'Sprawdź, jak dobrać powłokę do powierzchni i warunków pracy. Poznaj skład wyrobów lakierowych, metody aplikacji i ocenę właściwości po wyschnięciu.',
        'Porównaj odporność dwóch powłok i zaplanuj sprawdzenie ich przyczepności.',
        'Przemysł farb, laboratoria powłok i technologia zabezpieczeń powierzchni.'),
    POSTGRADUATE['WM']: (
        'Poznaj wózki, napędy, hamulce oraz zagadnienia utrzymania pojazdów szynowych. Rozwijaj wiedzę przydatną przy diagnozowaniu usterek i planowaniu obsługi taboru.',
        'Opracuj plan kontroli elementu taboru pracującego pod zmiennym obciążeniem.',
        'Producenci taboru, eksploatacja, diagnostyka oraz organizacja utrzymania.'),
}

IMAGES = {
    'kampus-pk.jpg': ('Budynek główny PK • Politechnika Krakowska, CC0 1.0',
                      'https://commons.wikimedia.org/wiki/File:Budynek_siedziby_Politechniki_Krakowskiej.jpg'),
    'makieta.jpg': ('Makieta • THOR, CC BY 2.0',
                   'https://commons.wikimedia.org/wiki/File:Architectural_Model_(4240901895).jpg'),
    'laboratorium.jpg': ('Zdjęcie ilustracyjne • Alexander Bogatyrev, CC BY 4.0',
                          'https://commons.wikimedia.org/wiki/File:Work_in_process.jpg'),
    'pracownia-komputerowa.jpg': ('Pracownia komputerowa • Mike1024, domena publiczna',
                                 'https://commons.wikimedia.org/wiki/File:Computer_lab_showing_desktop_PCs_warwick.jpg'),
    'elektronika.jpg': ('Raspberry Pi 4 • Laserlicht, CC BY-SA 4.0',
                       'https://commons.wikimedia.org/wiki/File:Raspberry_Pi_4_Model_B_-_Side.jpg'),
    'most.jpg': ('Most Świętokrzyski • Ewa Dryjańska, CC BY-SA 3.0',
                 'https://commons.wikimedia.org/wiki/File:Most_Swietokrzyski.JPG'),
    'materialy.jpg': ('Perlit pod mikroskopem • Michelshock, domena publiczna',
                      'https://commons.wikimedia.org/wiki/File:Pearlite.jpg'),
    'energia.jpg': ('Elektrownia wiatrowa • Andrzej Dworaczek, CC BY 4.0',
                     'https://commons.wikimedia.org/wiki/File:Wind_Power_Plant.jpg'),
    'robotyka.jpg': ('Ramię robota • Nenad Stojković (Shixart1985), CC BY 2.0',
                     'https://commons.wikimedia.org/wiki/File:Robot_arm_works_on_a_small_component_in_a_lab_setting.jpg'),
}
FACULTY_IMAGES = {
    'WA': 'makieta.jpg', 'WIiM': 'pracownia-komputerowa.jpg', 'WIEiK': 'elektronika.jpg',
    'WILiT': 'most.jpg', 'WIMiF': 'materialy.jpg', 'WIŚiE': 'energia.jpg',
    'WIiTCh': 'laboratorium.jpg', 'WM': 'robotyka.jpg',
}

CAMPUS_CARDS = [
    ('Gdzie uczymy się w Krakowie?', 'Zobacz kampusy przy Warszawskiej, w Czyżynach oraz przy Lea i Podchorążych. Mapa pomoże Ci znaleźć budynki i sprawdzić trasę dojazdu.', 'Mapa kampusów', CAMPUS_MAP),
    ('Akademiki i codzienne sprawy', 'Sprawdź położenie domów studenckich, zasady zakwaterowania oraz kontakty do administracji.', 'Zobacz akademiki', 'https://akademiki.pk.edu.pl/'),
    ('Koła naukowe i zespoły projektowe', 'Jeśli chcesz budować prototypy, prowadzić badania lub startować w konkursach, sprawdź zespoły działające przy wydziałach.', 'Znajdź koło naukowe', 'https://pk.edu.pl/student/studia/kola-naukowe/'),
    ('Organizacje studenckie', 'Poznaj samorząd, stowarzyszenia oraz społeczności, które organizują wydarzenia i pomagają odnaleźć się na uczelni.', 'Zobacz organizacje', 'https://pk.edu.pl/student/studia/organizacje-i-stowarzyszenia-studenckie/'),
    ('Stypendia i wsparcie', 'Zobacz, jakie świadczenia są dostępne, kiedy składać wnioski i z kim skontaktować się w swojej sprawie.', 'Sprawdź świadczenia', 'https://pk.edu.pl/student/studia/swiadczenia-dla-studentow/'),
    ('Wymiana międzynarodowa', 'Sprawdź uczelnie partnerskie i możliwości wyjazdu w ramach Erasmus+.', 'Zobacz uczelnie partnerskie', 'https://erasmus.pk.edu.pl/uczelnie-partnerskie/'),
]

DISCOVERY_CARDS = [
    ('Projekty studenckie', 'Zobacz, jak FutureLab pomaga zespołom przejść od pomysłu do prototypu. To dobry punkt wyjścia, jeśli szukasz miejsca na własny projekt.', 'Poznaj FutureLab', FUTURELAB_URL),
    ('Od projektu do pracy', 'Zobacz przykłady współpracy PK z firmami i partnerami przemysłowymi. Biuro Karier pomaga zaplanować pierwszą praktykę i przygotować się do rozmowy rekrutacyjnej.', 'Zobacz współpracę z biznesem', 'https://pk.edu.pl/politechnika/aktualnosci/?kategoria=wspolpraca'),
    ('Politechnika dla szkół', 'Zanim wybierzesz studia, sprawdź, co uczelnia przygotowała dla szkół i uczniów. Możesz poznać kierunki, zanim nadejdzie czas składania dokumentów.', 'Otwórz ofertę dla szkół', 'https://szkoly.pk.edu.pl/uczelnia-w-szkolach/'),
    ('80 lat Politechniki', 'Politechnika Krakowska świętowała 80-lecie w 2025 roku. Poznaj jej historię, sylwetki związanych z nią osób i jubileuszowe wydarzenia.', 'Poznaj historię uczelni', 'https://www.pk.edu.pl/index.php?Itemid=415&catid=2&id=5628%3Apolitechnika-krakowska-ma-80-lat-jubileusz-pelen-nauki-techniki-kultury-i-sztuki&lang=pl&option=com_content&view=article'),
]
