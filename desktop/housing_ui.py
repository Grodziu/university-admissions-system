from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QMessageBox, QWidget

from admissions.campus import HOUSING_FEES, HOUSING_MAP, HOUSING_URL
from .campus_map import CampusMap
from .discover import website
from .pages import date
from .widgets import MUTED, NAVY, box, button, card, chip, label

TEAL = '#147D69'


def km(value):
    return f'{float(value):.2f}'.replace('.', ',') + ' km'


class ResidenceIllustration(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(126, 84)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#CFE9EA'))
        painter.drawEllipse(QPointF(94, 32), 27, 27)
        for x, top, color in [(13, 35, '#6297AB'), (38, 18, '#214E74'),
                              (63, 29, '#337F8B'), (88, 40, '#719E87')]:
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(x, top, 21, 71 - top), 3, 3)
            painter.setBrush(QColor('#F2F8FC'))
            for y in range(top + 8, 63, 10):
                for dx in (5, 12):
                    painter.drawRoundedRect(QRectF(x + dx, y, 4, 5), 1, 1)
        painter.setPen(QPen(QColor('#85A9AB'), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(5, 73), QPointF(120, 73))


class HousingPages:
    def page_housing(self):
        data = self.data['housing']
        self.title('Akademiki', 'Osiedle Studenckie Politechniki Krakowskiej w Czyżynach')
        if self.role == 'candidate':
            self.candidate_housing(data)
        else:
            self.housing_statistics(data)
        self.content.addStretch()

    def candidate_housing(self, data):
        campaign_id = self.data['campaign']['id']
        request = data['request']
        selected_code = request['allocated']['code'] if request and request['allocated'] else request['preferred'] if request else ''
        status, status_layout = card(17)
        status_row = box(horizontal=True, spacing=20)
        status_layout.addLayout(status_row)
        status_fields = box(spacing=9)
        status_row.addLayout(status_fields, 7)
        status_fields.addWidget(label('Twój wniosek', 19, NAVY, True))
        status_fields.addWidget(chip(request['label'] if request else 'Brak wniosku'))
        if request and request['allocated']:
            dorm = request['allocated']
            status_fields.addWidget(label(f"Gratulacje! Twój akademik to {dorm['code']} „{dorm['name']}”.", 15, TEAL, True, True))
            status_fields.addWidget(label('Skontaktuj się z administracją osiedla, aby sprawdzić termin, dokumenty do zakwaterowania i dane do wpłaty.', 13, MUTED, wrap=True))
        elif not data['published']:
            status_fields.addWidget(label(f"Składanie wniosków do {date(data['ends_at'])}. Wyniki pojawią się po zakończeniu wszystkich tur.",
                                          13, MUTED, wrap=True))
            if data['my_distance'] is None:
                status_fields.addWidget(button('Ustal położenie adresu w profilu', lambda: self.navigate('profile'), secondary=True))
            else:
                status_fields.addWidget(label(f"{km(data['my_distance'])} w linii prostej od adresu zamieszkania do kampusu Warszawska.",
                                              13, NAVY, True, True))
                if request and request['status'] == 'pending' and request['distance'] != data['my_distance']:
                    status_fields.addWidget(label(f"We wniosku zapisana jest odległość {km(request['distance'])}. Zapisz preferencję ponownie, aby użyć aktualnego adresu.",
                                                  13, '#805015', wrap=True))
            if data['block']:
                status_fields.addWidget(label(data['block'], 13, '#805015', wrap=True))
        elif not request:
            status_fields.addWidget(label('W tej edycji zakończono rozpatrywanie wniosków.', 13, MUTED, wrap=True))
        summary = QFrame()
        summary.setObjectName('housing-residence-summary')
        summary.setStyleSheet(
            'QFrame#housing-residence-summary { border:1px solid #D7E8ED; border-radius:12px; '
            'background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #EAF2FA,stop:1 #EDF7F3); }'
        )
        summary_row = box(summary, horizontal=True, margins=12, spacing=8)
        summary_row.addWidget(ResidenceIllustration())
        summary_text = box(spacing=3)
        summary_text.addWidget(label('Osiedle w Czyżynach', 15, NAVY, True, True))
        summary_text.addWidget(label(f"{len(data['dorms'])} domy studenckie", 12, TEAL, True, True))
        seats = f"{data['capacity']:,}".replace(',', '\u202f')
        summary_text.addWidget(label(f'{seats} miejsc w tej edycji', 12, MUTED, wrap=True))
        summary_row.addLayout(summary_text, 1)
        status_row.addWidget(summary, 4)
        self.content.addWidget(status)

        tile_row = box(horizontal=True, spacing=16)
        left, options = card(16)
        options.addWidget(label('Wybierz preferowany dom', 19, NAVY, True, True))
        options.addWidget(label('Odległość decyduje o przyznaniu miejsca, a punkty rekrutacyjne o pierwszeństwie wyboru domu.', 12, MUTED, wrap=True))
        map_widget = CampusMap(data)
        choices = {}
        current = selected_code
        for dorm in data['dorms']:
            code = dorm['code']
            choice = button(f"{code} · {dorm['name']}   |   {dorm['address']}",
                            lambda _=False, value=code: select(value), secondary=True)
            choice.setCheckable(True)
            choices[code] = choice
            options.addWidget(choice)
        options.addStretch()
        selection = button('Zapisz preferencję' if request and request['status'] == 'pending' else 'Złóż wniosek o akademik',
                           lambda: self.mutate({'action': 'housing_apply', 'campaign_id': campaign_id, 'preferred': current}))
        if not data['published']:
            options.addWidget(selection)
        if not data['published'] and request and request['status'] == 'pending':
            def withdraw():
                if QMessageBox.question(self, 'Wniosek o akademik', 'Wycofać wniosek o miejsce?') == QMessageBox.StandardButton.Yes:
                    self.mutate({'action': 'housing_withdraw', 'campaign_id': campaign_id})
            options.addWidget(button('Wycofaj wniosek', withdraw, danger=True))
        tile_row.addWidget(left, 5)

        right, view = card(16)
        view.addWidget(label('Domy studenckie przy ul. Skarżyńskiego', 18, NAVY, True, True))
        view.addWidget(map_widget)
        view.addWidget(map_widget.attribution())
        details = label('', 13, MUTED, wrap=True)
        view.addWidget(details)
        links = box(horizontal=True, spacing=8)
        links.addWidget(website('Osiedle i mapa', HOUSING_MAP), 1)
        links.addWidget(website('Cennik', HOUSING_FEES), 1)
        if request and request['allocated']:
            links.addWidget(website('Zakwaterowanie', HOUSING_URL), 1)
        view.addLayout(links)
        tile_row.addWidget(right, 6)
        self.content.addLayout(tile_row)

        def select(code):
            nonlocal current
            current = code
            map_widget.highlight(code)
            for key, control in choices.items():
                control.setChecked(key == code)
                control.setProperty('active', key == code)
                control.style().unpolish(control)
                control.style().polish(control)
            entry = next((d for d in data['dorms'] if d['code'] == code), None)
            details.setText(f"{entry['description']} Liczba miejsc w tej edycji: {entry['seats']}."
                            if entry else 'Wybierz punkt na mapie lub dom z listy, aby zobaczyć ofertę.')
            selection.setEnabled(bool(code) and not data['block'])

        map_widget.selected.connect(select)
        select(selected_code)

    def housing_statistics(self, data):
        counts = data['counts']
        metrics = box(horizontal=True)
        for title, number in [('Miejsca w edycji', data['capacity']),
                              ('Wnioski oczekujące', counts.get('pending', 0)),
                              ('Zakwaterowanie przyznane', counts.get('awarded', 0)),
                              ('Wnioski na rezerwie', counts.get('reserve', 0))]:
            total, fields = card(14)
            fields.addWidget(label(f'{number:,}'.replace(',', '\u202f'), 29, NAVY, True))
            fields.addWidget(label(title, 12, MUTED, wrap=True))
            metrics.addWidget(total, 1)
        self.content.addLayout(metrics)
        row = box(horizontal=True, spacing=16)
        panel, body = card(16)
        body.addWidget(label('Odległość od kampusu Warszawska', 19, NAVY, True, True))
        coverage = CampusMap(data, overview=True)
        body.addWidget(coverage)
        body.addWidget(coverage.attribution())
        distance = data['min_distance']
        text = f'Najmniejsza odległość wśród przyjętych: {km(distance)}.' if distance is not None else (
            'W tej edycji nie przyznano miejsc.' if data['published'] else 'Okrąg pojawi się po rozpatrzeniu wniosków na koniec naboru.')
        if distance is not None and not data['cutoff_used']:
            text += ' Miejsca wystarczyły dla wszystkich uprawnionych wniosków.'
        body.addWidget(label(text, 13, MUTED, wrap=True))
        row.addWidget(panel, 6)
        homes, fields = card(16)
        fields.addWidget(label('Rozkład miejsc', 19, NAVY, True))
        for dorm in data['dorms']:
            used = data['per_dorm'].get(dorm['code'], 0)
            fields.addWidget(label(f"{dorm['code']} · {dorm['name']}   {used} / {dorm['seats']}", 14, NAVY, True, True))
        fields.addStretch()
        fields.addWidget(website('Osiedle Studenckie PK', HOUSING_MAP))
        row.addWidget(homes, 4)
        self.content.addLayout(row)
