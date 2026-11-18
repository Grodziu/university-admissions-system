from admissions.campus import ACCOUNTS, ADAPCIAK, DELTA, DEPARTMENT_PLANS, SCHEDULES
from .discover import website
from .widgets import MUTED, NAVY, box, card, chip, label


def onboarding(offer):
    launched = offer['state'] == 'launched'
    panel, body = card(18)
    body.addWidget(chip('Kierunek uruchomiony' if launched else 'Minimum uruchomienia osiągnięte', '#146451', '#E4F3EC'))
    body.addWidget(label('Przygotuj się do pierwszych zajęć', 19, NAVY, True, True))
    body.addWidget(label(
        'Po rekrutacji sprawdź powiadomienia i pocztę, a następnie aktywuj konto do Teams, Outlooka i Delty według instrukcji PK.',
        13, MUTED, wrap=True))
    row = box(horizontal=True, spacing=8)
    plan_url = DEPARTMENT_PLANS.get(offer['faculty'])
    row.addWidget(website('Plan zajęć wydziału' if plan_url else 'Gdzie znaleźć plan zajęć', plan_url or SCHEDULES), 1)
    row.addWidget(website('Aktywacja konta PK', ACCOUNTS), 1)
    row.addWidget(website('Delta', DELTA))
    body.addLayout(row)
    body.addWidget(label('Poznaj osoby z pierwszego roku na Adapciaku, wyjeździe integracyjnym dla nowych studentów PK.',
                         13, MUTED, wrap=True))
    body.addWidget(website('Poznaj Adapciaka', ADAPCIAK))
    return panel
