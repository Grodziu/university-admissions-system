"""Curated PK names. Admission rules, dates and capacities belong to this project."""
INFORMATOR = 'Informator PK 2027/28, s. 5–7 (plik dostarczony przez zespół)'
DEGREES_SOURCE = 'https://rekrutacja.pk.edu.pl/liczba-miejsc-na-pierwszym-roku-stacjonarnych-i-niestacjonarnych-studiow-i-i-ii-stopnia/'
PG_SOURCE = 'https://pk.edu.pl/kandydat/studia-podyplomowe/studia-podyplomowe-oferta/'
FACULTIES = [
    ('WA', 'Wydział Architektury', '#009EE3'),
    ('WIiM', 'Wydział Informatyki i Matematyki', '#77A43F'),
    ('WIEiK', 'Wydział Inżynierii Elektrycznej i Komputerowej', '#714696'),
    ('WILiT', 'Wydział Inżynierii Lądowej i Transportu', '#8192C9'),
    ('WIMiF', 'Wydział Inżynierii Materiałowej i Fizyki', '#D3682B'),
    ('WIŚiE', 'Wydział Inżynierii Środowiska i Energetyki', '#006EAA'),
    ('WIiTCh', 'Wydział Inżynierii i Technologii Chemicznej', '#008B8B'),
    ('WM', 'Wydział Mechaniczny', '#AF0A7F'),
]
# name, modes I, modes II, short original editorial description
PROGRAMS = {
    'WA': [('Architektura', 'SN', 'S', 'Projektuj przestrzenie, w których chce się żyć. Połącz wyobraźnię, technikę i odpowiedzialność za miasto.'),
           ('Architektura krajobrazu', 'S', 'S', 'Twórz zielone przestrzenie: od ogrodu po krajobraz miasta. Łącz projektowanie z wiedzą o przyrodzie.')],
    'WIiM': [('Informatyka', 'SN', 'SN', 'Buduj oprogramowanie, analizuj dane i poznawaj algorytmy. Rozwijaj pomysły w działające rozwiązania.'),
             ('Matematyka stosowana', 'S', 'S', 'Odkrywaj modele, które opisują rzeczywistość. Wykorzystuj matematykę w analizie danych i technologii.')],
    'WIEiK': [('Elektrotechnika i automatyka', 'SN', 'SN', 'Projektuj inteligentne układy sterowania i nowoczesne systemy elektryczne.'),
              ('Informatyka w inżynierii komputerowej', 'SN', '', 'Poznaj drogę od elektroniki do oprogramowania i połącz świat urządzeń z informatyką.'),
              ('Infotronika', '', 'SN', 'Łącz elektronikę, informatykę i automatykę w złożonych systemach technicznych.')],
    'WILiT': [('Budownictwo', 'SN', 'SN', 'Projektuj i realizuj bezpieczne konstrukcje. Poznaj materiały, obliczenia i cyfrowe narzędzia inżyniera.'),
              ('Transport i logistyka', 'SN', 'SN', 'Usprawniaj podróże i przepływ towarów. Twórz transport przyjazny ludziom i otoczeniu.')],
    'WIMiF': [('Fizyka techniczna', 'S', 'S', 'Zamieniaj odkrycia fizyki w technologię. Pracuj z pomiarami, modelowaniem i nowymi urządzeniami.'),
              ('Inżynieria materiałowa', 'SN', 'SN', 'Poznaj materiały, które zmieniają przemysł: od metali po zaawansowane kompozyty.')],
    'WIŚiE': [('Energetyka', 'S', 'SN', 'Projektuj odpowiedzialne systemy energii. Poznaj źródła odnawialne, wytwarzanie i efektywność energetyczną.'),
              ('Inżynieria środowiska', 'S', 'SN', 'Dbaj o wodę, powietrze i zasoby. Twórz infrastrukturę, która poprawia jakość życia.')],
    'WIiTCh': [('Biotechnologia przemysłowa', 'S', 'S', 'Wykorzystuj procesy biologiczne w przemyśle i rozwijaj technologie przyszłości.'),
               ('Technologia chemiczna', 'S', 'S', 'Od laboratorium do produkcji: projektuj procesy i produkty z wykorzystaniem nowoczesnej chemii.')],
    'WM': [('Mechanika i budowa maszyn', 'SN', 'SN', 'Projektuj mechanizmy i maszyny. Łącz modelowanie, wytwarzanie i praktykę inżynierską.'),
           ('Informatyka stosowana', 'S', 'S', 'Rozwijaj oprogramowanie do zastosowań inżynierskich, obliczeń i sterowania.')],
}
POSTGRADUATE = {
    'WA': 'Building Information Modelling (BIM) – technologie cyfrowe w projektowaniu architektoniczno-budowlanym',
    'WIiM': 'Analiza danych i uczenie maszynowe',  # Illustrative project offer; not presented as an official PK programme.
    'WIEiK': 'Bezpieczeństwo infrastruktury krytycznej i kluczowej w zakresie systemów przemysłowych Operational Technology (OT)',
    'WILiT': 'Inżynieria ruchu drogowego',
    'WIMiF': 'Międzynarodowy/Europejski Inżynier Spawalnik IWE',
    'WIŚiE': 'Eksploatacja i zarządzanie systemami wodociągowymi i kanalizacyjnymi',
    'WIiTCh': 'Wyroby lakierowe. Technologia i zastosowanie',
    'WM': 'Budowa i eksploatacja pojazdów szynowych',
}


def technicians(names):
    return ['technik ' + n.strip() for n in names.split('|')]


PROFESSIONS = {
    'Architektura krajobrazu': technicians('architektury krajobrazu'),
    'Elektrotechnika i automatyka': technicians('automatyk|elektroenergetyk transportu szynowego|elektronik|elektroniki i informatyki medycznej|elektryk|energetyk|mechatronik|szerokopasmowej komunikacji elektronicznej|teleinformatyk|telekomunikacji'),
    'Informatyka w inżynierii komputerowej': technicians('automatyk|elektronik|elektroniki i informatyki medycznej|informatyk|łączności|mechatronik|programista|szerokopasmowej komunikacji elektronicznej|teleinformatyk|telekomunikacji'),
    'Budownictwo': technicians('budownictwa|budownictwa kolejowego|budownictwa wodnego|budowy dróg|dróg kolejowych i obiektów inżynieryjnych|geodeta|robót wykończeniowych w budownictwie'),
    'Transport i logistyka': technicians('automatyk sterowania ruchem kolejowym|elektroenergetyk transportu szynowego|eksploatacji portów i terminali|logistyk|lotniskowych służb operacyjnych|spedytor|transportu drogowego|transportu kolejowego'),
    'Fizyka techniczna': technicians('automatyk|dźwięku|elektronik|elektroniki i informatyki medycznej|elektroniki medycznej|elektryk|energetyk|informatyk|kryminalistyki|mechanik precyzyjny|metrolog|programista|teleinformatyk|telekomunikacji'),
    'Inżynieria materiałowa': technicians('ceramik|hutnik|informatyk|kryminalistyki|mechanik|mechanik lotniczy|mechanik precyzyjny|odlewnik|pojazdów samochodowych|przemysłu metalurgicznego|spawalnictwa|technologii chemicznej|technologii ceramicznej'),
    'Biotechnologia przemysłowa': technicians('analityk|ochrony środowiska|technologii chemicznej'),
    'Technologia chemiczna': technicians('analityk|ochrony środowiska|technologii chemicznej'),
    'Informatyka stosowana': technicians('elektronik|informatyk|łączności|programista|teleinformatyk'),
    'Mechanika i budowa maszyn': technicians('automatyk|automatyk sterowania ruchem kolejowym|chłodnictwa i klimatyzacji|informatyk|mechanik|mechatronik|pojazdów samochodowych|teleinformatyk|urządzeń dźwigowych'),
}
# Project's simplified subject policy; distinct from the official PK calculation formula.
SUBJECTS = {
    'WA': ['matematyka', 'fizyka', 'historia sztuki', 'geografia', 'biologia'],
    'WIiM': ['matematyka', 'fizyka', 'informatyka'],
    'WIEiK': ['matematyka', 'fizyka', 'informatyka'],
    'WILiT': ['matematyka', 'fizyka', 'informatyka', 'chemia', 'geografia'],
    'WIMiF': ['matematyka', 'fizyka', 'informatyka', 'chemia', 'biologia'],
    'WIŚiE': ['matematyka', 'fizyka', 'informatyka', 'chemia', 'biologia', 'geografia'],
    'WIiTCh': ['matematyka', 'fizyka', 'informatyka', 'chemia', 'biologia'],
    'WM': ['matematyka', 'fizyka', 'informatyka', 'chemia'],
}
