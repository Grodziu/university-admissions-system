"""Versioned project criteria; these are not the official PK admission regulations."""
BONUS_CATALOG = [
    {'code': '', 'points': 0, 'title': 'Bez premii', 'evidence': 'Brak udokumentowanego osiągnięcia lub brak podstaw do premii.'},
    {'code': 'school', 'points': 10, 'title': 'Wyróżnienie szkolne / lokalne', 'evidence': 'Dyplom laureata konkursu szkolnego lub lokalnego albo podium lokalnych zawodów sportowych.'},
    {'code': 'regional_final', 'points': 20, 'title': 'Finalista etapu wojewódzkiego', 'evidence': 'Zaświadczenie o udziale w finale wojewódzkim konkursu, olimpiady lub zawodów.'},
    {'code': 'regional_winner', 'points': 30, 'title': 'Laureat etapu wojewódzkiego', 'evidence': 'Dyplom laureata / miejsca na podium w finale wojewódzkim.'},
    {'code': 'national_final', 'points': 40, 'title': 'Finalista etapu ogólnopolskiego', 'evidence': 'Zaświadczenie o osiągnięciu finału ogólnopolskiego konkursu, olimpiady lub zawodów.'},
    {'code': 'national_winner', 'points': 50, 'title': 'Laureat ogólnopolski lub międzynarodowy', 'evidence': 'Dyplom laureata / podium na szczeblu ogólnopolskim lub międzynarodowym.'},
]
BONUS_BY_CODE = {row['code']: row for row in BONUS_CATALOG}
STATUS_HELP = {
    'draft': 'Uzupełnij dane i dokumenty, a następnie złóż zgłoszenie.',
    'submitted': 'Komisja sprawdza dokumenty, zdjęcie i potwierdzenie opłaty.',
    'correction': 'Popraw wskazane braki i złóż zgłoszenie ponownie przed końcem zapisów.',
    'verified': 'Komisja zatwierdziła dokumenty. Wynik i kwalifikacja pojawią się po publikacji listy.',
    'rejected': 'Komisja odrzuciła zgłoszenie. Przyczyna znajduje się poniżej.',
    'qualified': 'Masz miejsce na liście. Teraz kandydat musi potwierdzić chęć studiowania przed końcem tury.',
    'confirmed': 'Miejsce zostało potwierdzone.',
    'waitlist': 'Jesteś na liście rezerwowej. Możesz zgłosić się ponownie w kolejnej otwartej turze.',
    'expired': 'Dokumenty były poprawne, ale kandydat nie potwierdził miejsca w terminie. Możliwy jest udział w kolejnej turze.',
    'withdrawn': 'Kandydat wycofał zgłoszenie.',
    'canceled': 'Kierunek nie osiągnął minimum potwierdzonych miejsc i nie został uruchomiony.',
}
OATH_TEXT = ('Zobowiązuję się rzetelnie zdobywać wiedzę, szanować innych członków społeczności akademickiej, '
             'przestrzegać zasad uczciwości naukowej i odpowiedzialnie rozwijać swoje umiejętności. '
             'To ślubowanie w demonstracyjnym systemie projektu; nie stanowi rzeczywistego wpisu na studia.')
