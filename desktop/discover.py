from decimal import Decimal

from PySide6.QtCore import QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QLineEdit, QTextEdit, QWidget

from portable import ROOT
from .pages import DEGREES, date, dialog
from .pk_content import (CAMPUS_CARDS, CAMPUS_MAP, CAMPUS_URL, DISCOVERY_CARDS,
                         FACULTY_IMAGES, FEES_URL, IMAGES, INFORMATOR_URL,
                         PG_SOURCE, PROGRAMME_STORIES, SYLLABUS_URL)
from .visuals import tint, wr_formula
from .widgets import MUTED, NAVY, box, button, card, chip, combo, field, label, line_icon
from .offer_form import OfferTerms
from .programme_marks import ProgrammeMark


def website(text, url):
    link = button(text, lambda: QDesktopServices.openUrl(QUrl(url)), secondary=True)
    link.setIcon(line_icon('external', NAVY))
    return link


def image_credit(file):
    credit, url = IMAGES[file]
    item = label('', 10, MUTED)
    item.setTextFormat(Qt.TextFormat.RichText)
    item.setText(f'<a style="color:#53667E;" href="{url}">{credit}</a>')
    item.setOpenExternalLinks(True)
    item.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return item


class PhotoHero(QFrame):
    def __init__(self, title, subtitle, photo, actions, height=260, accent=NAVY):
        super().__init__()
        self.photo = QPixmap(str(ROOT / 'assets' / photo))
        self.accent = QColor(accent)
        self.accent.setAlpha(83)
        self.setMinimumHeight(height)
        outer = box(self, margins=26)
        self.panel = QWidget()
        text = box(self.panel, spacing=12)
        text.addWidget(label(title, 32, 'white', True, True))
        text.addWidget(label(subtitle, 15, '#E3EDF8', wrap=True))
        if actions:
            row = box(horizontal=True)
            for action in actions:
                row.addWidget(action)
            row.addStretch()
            text.addLayout(row)
        columns = box(horizontal=True, spacing=0)
        columns.addWidget(self.panel, 56)
        columns.addStretch(44)
        outer.addStretch(1)
        outer.addLayout(columns)
        outer.addStretch(1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(area, 16, 16)
        painter.setClipPath(clip)
        painter.fillRect(area, QColor('#062B55'))
        if not self.photo.isNull():
            picture = QRectF(area.width() * .31, 0, area.width() * .69, area.height())
            scale = max(picture.width() / self.photo.width(), picture.height() / self.photo.height())
            width = picture.width() / scale
            height = picture.height() / scale
            source = QRectF((self.photo.width() - width) / 2, (self.photo.height() - height) / 2, width, height)
            painter.drawPixmap(picture, self.photo, source)
        gradient = QLinearGradient(0, 0, area.width(), 0)
        gradient.setColorAt(.31, QColor('#062B55'))
        gradient.setColorAt(.5, QColor(6, 43, 85, 232))
        gradient.setColorAt(.8, QColor(6, 43, 85, 25))
        gradient.setColorAt(1, self.accent)
        painter.fillRect(area, gradient)
        painter.end()


class DiscoveryPages:
    def discovery_hero(self, title, subtitle, actions):
        hero = PhotoHero(title, subtitle, 'kampus-pk.jpg', actions, 244)
        hero.setFixedHeight(244)
        self.content.addWidget(hero)
        self.content.addWidget(image_credit('kampus-pk.jpg'))

    def page_discover(self):
        self.discovery_hero(
            'Zaprojektuj swoją przyszłość na PK',
            'Sprawdź, co możesz tworzyć na studiach technicznych w Krakowie i gdzie rozwijać własne projekty.',
            [button('Przeglądaj kierunki', lambda: self.navigate('catalog'), secondary=True)])
        materials, row = card(18)
        row.addWidget(label('Zaplanuj studia', 20, NAVY, True))
        links = box(horizontal=True)
        for title, url in [('Informator 2027/28', INFORMATOR_URL), ('Programy i sylabusy', SYLLABUS_URL),
                           ('Oferta podyplomowa', PG_SOURCE)]:
            links.addWidget(website(title, url), 1)
        row.addLayout(links)
        self.content.addWidget(materials)
        self.content.addWidget(button('Poznaj wykładowców i ich specjalizacje', lambda:self.navigate('lecturers'), secondary=True))
        self.content.addWidget(label('Poza zajęciami', 22, NAVY, True))
        self.resource_cards(DISCOVERY_CARDS)
        self.content.addWidget(button('Poznaj życie na PK', lambda: self.navigate('campus'), secondary=True))
        self.content.addStretch()

    def page_campus(self):
        self.discovery_hero(
            'Życie na PK', 'Znajdź swoje miejsce na kampusie, wejdź do zespołu projektowego i zobacz dostępne wsparcie.',
            [website('Kampusy Politechniki', CAMPUS_URL), website('Mapa', CAMPUS_MAP)])
        self.resource_cards(CAMPUS_CARDS)
        self.content.addStretch()

    def page_krakow(self):
        from .krakow import show_krakow
        show_krakow(self.content)

    def page_lecturers(self):
        from .lecturers import LecturerExplorer
        self.content.addWidget(LecturerExplorer())
        self.content.addStretch()

    def resource_cards(self, items):
        styles = [('discover', '#007CAD'), ('housing', '#147D69'), ('campus', '#714696'),
                  ('profile', '#955C19'), ('applications', '#A3236C'), ('external', '#1B609B')]
        for start in range(0, len(items), 2):
            row = box(horizontal=True, spacing=16)
            for i, (title, description, action, url) in enumerate(items[start:start + 2], start):
                icon, accent = styles[i % len(styles)]
                panel, body = card(18)
                panel.setStyleSheet(f'QFrame#card {{ border-left:4px solid {accent}; }}')
                heading = box(horizontal=True)
                mark = label('')
                mark.setPixmap(line_icon(icon, accent).pixmap(24, 24))
                heading.addWidget(mark)
                heading.addWidget(label(title, 19, NAVY, True, True), 1)
                body.addLayout(heading)
                body.addWidget(label(description, 14, MUTED, wrap=True))
                body.addStretch()
                body.addWidget(website(action, url))
                row.addWidget(panel, 1)
            self.content.addLayout(row)

    def page_catalog(self):
        staff = self.role in ['admin', 'commission']
        self.title('Kierunki i listy' if staff else 'Znajdź swój kierunek',
                   'Wybierz kierunek, aby zobaczyć stan listy dla danego trybu i stopnia.' if staff else
                   'Zobacz, czego możesz się nauczyć i gdzie wykorzystać te umiejętności. Wybierz stopień, wydział lub tryb.')
        saved = self.filters.get('catalog', {})
        row = box(horizontal=True)
        self.search = QLineEdit(saved.get('search', ''))
        self.search.setPlaceholderText('Szukaj kierunku…')
        self.search.setAccessibleName('Szukaj kierunku')
        self.degree_filter = combo(DEGREES, 'Stopień studiów')
        self.mode_filter = combo([('Każdy tryb', ''), ('Stacjonarne', 'S'), ('Niestacjonarne', 'N')], 'Tryb studiów')
        faculties = {o['faculty']: o['faculty_name'] for o in self.offers}
        self.faculty_filter = combo([('Wszystkie wydziały', '')] + [(f, f) for f in sorted(faculties)], 'Wydział')
        row.addWidget(self.search, 2)
        for key, item in [('degree', self.degree_filter), ('mode', self.mode_filter), ('faculty', self.faculty_filter)]:
            item.setCurrentIndex(max(0, item.findData(saved.get(key))))
            row.addWidget(item, 1)
        self.content.addLayout(row)
        summary = box(horizontal=True)
        self.catalog_count = label('', 13, MUTED, wrap=True)
        summary.addWidget(self.catalog_count, 1)
        self.batch_publish_button = None
        if staff:
            if self.data.get('can_create_offer'):
                summary.addWidget(button('Dodaj ofertę studiów', self.new_offer))
            self.batch_publish_button = button('Opublikuj gotowe listy…', self.select_publications, secondary=True)
            summary.addWidget(self.batch_publish_button)
        self.content.addLayout(summary)
        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(16)
        self.content.addWidget(container)
        self.content.addStretch()
        self.search.textChanged.connect(self.render_catalog)
        for item in [self.degree_filter, self.mode_filter, self.faculty_filter]:
            item.currentIndexChanged.connect(self.render_catalog)
        self.render_catalog()

    def render_catalog(self):
        filters = {'search': self.search.text(), 'degree': self.degree_filter.currentData(),
                   'mode': self.mode_filter.currentData(), 'faculty': self.faculty_filter.currentData()}
        self.filters['catalog'] = filters
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            widget.hide()
            widget.deleteLater()
        self.visible_offers = [o for o in self.offers if o['degree'] == filters['degree']
                               and (not filters['mode'] or o['mode'] == filters['mode'])
                               and (not filters['faculty'] or filters['faculty'] in [o['faculty']] + o['partners'])
                               and filters['search'].strip().casefold() in o['name'].casefold()]
        groups = {}
        for o in self.visible_offers:
            groups.setdefault((o['program_id'], o['degree']), []).append(o)
        staff = self.role in ['commission', 'admin']
        count = sum(o['publication_phase'] == 'ready' for o in self.visible_offers)
        self.catalog_count.setText(f'Kierunki: {len(groups)}  ·  Tryby: {len(self.visible_offers)}'
                                   + (f'  ·  Listy gotowe: {count}' if staff else ''))
        if self.batch_publish_button:
            self.batch_publish_button.setEnabled(bool(count))
            self.batch_publish_button.setToolTip('Listy pojawią się po zamknięciu zapisów i weryfikacji dokumentów.' if not count else '')
        cols = 3 if self.width() >= 1490 else 2
        for i, variants in enumerate(groups.values()):
            o = next((v for v in variants if v['mode'] == 'S'), variants[0])
            frame, content = card(18)
            frame.setStyleSheet(f"QFrame#card {{background:white; border:1px solid #DEE6F1; border-top:5px solid {o['color']}; border-radius:14px;}}")
            heading = box(horizontal=True)
            titles = box(spacing=6)
            titles.addWidget(chip(o['faculty'] + (' + ' + ', '.join(o['partners']) if o['partners'] else ''), NAVY, tint(o['color'])))
            titles.addWidget(label(o['name'], 22, NAVY, True, True))
            titles.addWidget(label(o['faculty_name'], 12, MUTED, wrap=True))
            heading.addLayout(titles, 1)
            heading.addWidget(ProgrammeMark(o), 0, Qt.AlignmentFlag.AlignTop)
            content.addLayout(heading)
            modes = box(horizontal=True, spacing=6)
            for variant in sorted(variants, key=lambda v: v['mode'] != 'S'):
                modes.addWidget(chip(variant['mode_label']))
            modes.addStretch()
            content.addLayout(modes)
            content.addStretch()
            if staff:
                for variant in variants:
                    content.addWidget(label(f"{variant['mode_label']} · {variant['publication_message']}", 12, MUTED, wrap=True))
            else:
                pitch = PROGRAMME_STORIES.get(o['name'], (o['description'], '', ''))[0]
                content.addWidget(label(pitch, 13, wrap=True))
            content.addWidget(button('Otwórz listy  →' if staff else 'Poznaj kierunek  →',
                                     lambda checked=False, offer=o: self.offer_dialog(offer), secondary=True))
            self.grid.addWidget(frame, i // cols, i % cols)
        for col in range(cols):
            self.grid.setColumnStretch(col, 1)
        if not groups:
            self.grid.addWidget(label('Brak kierunków pasujących do filtrów.', 16, MUTED), 0, 0)

    def offer_dialog(self, offer):
        staff = self.role in ['commission', 'admin']
        d = dialog(self, offer['name'], offer['faculty_name'] + ' · ' + offer['degree_label'], 890, accent=offer['color'])
        variants = [o for o in self.offers if (o['program_id'], o['degree']) == (offer['program_id'], offer['degree'])]
        chooser = combo([(o['mode_label'], o['id']) for o in sorted(variants, key=lambda o: o['mode'] != 'S')], 'Tryb studiów')
        chooser.setCurrentIndex(chooser.findData(offer['id']))
        chooser.setVisible(len(variants) > 1)
        variant_row = box(horizontal=True)
        variant_row.addWidget(label('Tryb studiów' if len(variants) > 1 else offer['mode_label'], 13, NAVY, True))
        variant_row.addWidget(chooser, 1)
        d.form.addLayout(variant_row)
        content = QWidget()
        layout = box(content, spacing=14)
        d.form.addWidget(content)
        actions = QWidget()
        row = box(actions, horizontal=True, spacing=8)
        d.buttons.addWidget(actions)

        def render():
            for area in [layout, row]:
                while area.count():
                    widget = area.takeAt(0).widget()
                    widget.hide()
                    widget.deleteLater()
            o = next(v for v in variants if v['id'] == chooser.currentData())
            if staff:
                self.staff_offer(d, o, layout, row)
            else:
                self.describe_offer(d, o, layout, row)

        chooser.currentIndexChanged.connect(render)
        render()
        d.resize(890, 780)
        d.exec()

    def describe_offer(self, d, o, layout, actions):
        pitch, project, career = PROGRAMME_STORIES.get(o['name'], (o['description'], '', ''))
        image = FACULTY_IMAGES.get(o['faculty'], 'kampus-pk.jpg')
        title = {'I': 'Czego się nauczysz?', 'II': 'Rozwiń swój warsztat', 'PG': 'Czego możesz użyć w pracy?'}[o['degree']]
        layout.addWidget(PhotoHero(title, pitch, image, [], 200, accent=o['color']))
        layout.addWidget(image_credit(image))
        panel, body = card(16)
        if project:
            body.addWidget(label('Przykład zadania', 16, NAVY, True))
            body.addWidget(label(project, 14, wrap=True))
            body.addWidget(label('Gdzie przydadzą się te umiejętności?', 16, NAVY, True))
            body.addWidget(label(career, 14, MUTED, wrap=True))
        tuition = o['tuition_per_semester']
        if tuition is not None:
            integer, cents = f'{Decimal(tuition):,.2f}'.split('.')
            value = integer.replace(',', '\u202f') + ',' + cents
            body.addWidget(chip(f'Czesne przykładowe · {value} zł / semestr'))
        body.addWidget(website('Oferta studiów podyplomowych PK' if o['degree'] == 'PG' else 'Sylabusy i plan studiów PK',
                               PG_SOURCE if o['degree'] == 'PG' else SYLLABUS_URL))
        if o['illustrative']:
            body.addWidget(label('Przykładowy program studiów.', 12, MUTED))
        layout.addWidget(panel)
        if o['state'] == 'canceled':
            layout.addWidget(chip(o['state_label'], '#A73535', '#FFF3F2'))
        if self.role == 'candidate':
            existing = next((a for a in self.data['applications'] if a['offer_id'] == o['id']), None)
            if o['open']:
                layout.addWidget(label(f"Zgłoszenia do {date(o['application_end'])}", 13, MUTED))
            elif not existing:
                layout.addWidget(label(o['block_reason'], 13, MUTED, wrap=True))
            if existing:
                actions.addWidget(button('Moje zgłoszenie', lambda: (d.accept(), self.application_dialog(existing))))
            elif o['open']:
                def apply():
                    self.current = 'applications'
                    self.mutate({'action': 'create_application', 'offer_id': o['id']}, d)
                actions.addWidget(button('Utwórz zgłoszenie', apply))
        actions.insertWidget(0, button('Zasady rekrutacji', lambda: self.admission_rules(d, o), secondary=True))

    def staff_offer(self, d, o, layout, actions):
        panel, body = card(18)
        body.addWidget(chip(o['publication_message'], NAVY, tint(o['color'])) if len(o['publication_message']) < 60
                       else label(o['publication_message'], 15, NAVY, True, True))
        summary = box(horizontal=True)
        for title, value in [('Do weryfikacji', o['pending_review']),
                             ('Oczekują na potwierdzenie', o['awaiting_confirmation']),
                             ('Potwierdzone miejsca', o['confirmed'])]:
            metric, content = card(12)
            content.addWidget(label(title, 12, MUTED, wrap=True))
            content.addWidget(label(value, 27, NAVY, True))
            summary.addWidget(metric, 1)
        body.addLayout(summary)
        if not o['configurable']:
            body.addWidget(label(f"Limit miejsc: {o['capacity']} · Minimum uruchomienia: {o['minimum']} · {o['state_label']}", 13, MUTED,
                                 wrap=True))
        if o['round_end']:
            body.addWidget(label(f"Potwierdzanie miejsca do {date(o['round_end'])}", 13, MUTED, wrap=True))
        if o['threatened']:
            body.addWidget(label('Mało aktywnych kandydatów w stosunku do minimum uruchomienia.', 13, '#996020', wrap=True))
        layout.addWidget(panel)
        if o['configurable']:
            settings, fields = card(18)
            fields.addWidget(label('Warunki oferty', 19, NAVY, True))
            fields.addWidget(label('Zapisz warunki przed rozpoczęciem pierwszej tury i wpłynięciem zgłoszeń.', 13, MUTED, wrap=True))
            terms = OfferTerms(self.data, o)
            terms.set_variant(o['degree'], o['mode'])
            fields.addWidget(terms)
            fields.addWidget(button('Zapisz warunki oferty', lambda: self.mutate(
                {'action': 'configure_offer', 'offer_id': o['id'], **terms.values()}, d,
                done=lambda _: self.statusBar().showMessage('Zapisano warunki oferty.', 6000))))
            layout.addWidget(settings)
        else:
            actions.addWidget(button('Zasady i opłaty', lambda: self.admission_rules(d, o), secondary=True))
        actions.addWidget(button('Ranking na żywo', lambda: self.ranking_dialog(o), secondary=True))
        actions.addWidget(button('Opublikowane listy', lambda: self.publication_dialog(o), secondary=True))
        if o['publication_phase'] == 'ready':
            actions.addWidget(button('Opublikuj wyniki', lambda: self.mutate(
                {'action': 'publish', 'offer_id': o['id'], 'expected_round': o['round']}, d)))

    def new_offer(self):
        campaign = self.data['campaign']
        eligible = {r['degree'] for r in campaign['rounds'] if r['number'] == 1 and r['start'] > campaign['now']}
        d = dialog(self, 'Dodaj ofertę studiów', 'Wybierz wydział i zdefiniuj warunki dla stopnia i trybu.', 790)
        name = field(d.form, 'Nazwa kierunku')
        faculty = combo([(f["name"], f['id']) for f in self.data['faculties']], 'Wydział')
        degree = combo([entry for entry in DEGREES if entry[1] in eligible], 'Stopień studiów')
        mode = combo([('Stacjonarne', 'S'), ('Niestacjonarne', 'N')], 'Tryb studiów')
        for title, control in [('Wydział', faculty), ('Stopień studiów', degree), ('Tryb studiów', mode)]:
            d.form.addWidget(label(title, 12, MUTED, True))
            d.form.addWidget(control)
        description = QTextEdit()
        description.setPlaceholderText('Opis nowego kierunku dla kandydatów')
        description.setMaximumHeight(92)
        d.form.addWidget(description)
        terms = OfferTerms(self.data)
        d.form.addWidget(terms)

        def select_degree():
            postgraduate = degree.currentData() == 'PG'
            if postgraduate:
                mode.setCurrentIndex(mode.findData('N'))
            mode.setEnabled(not postgraduate)
            terms.minimum.setText('20' if degree.currentData() == 'I' else '10')
            terms.set_variant(degree.currentData(), mode.currentData())

        degree.currentIndexChanged.connect(select_degree)
        mode.currentIndexChanged.connect(lambda: terms.set_variant(degree.currentData(), mode.currentData()))
        select_degree()
        d.buttons.addWidget(button('Utwórz ofertę', lambda: self.mutate({
            'action': 'create_offer', 'campaign_id': campaign['id'], 'faculty_id': faculty.currentData(),
            'name': name.text(), 'description': description.toPlainText(), 'degree': degree.currentData(),
            'mode': mode.currentData(), **terms.values()}, d)))
        d.resize(790, 790)
        d.exec()

    def admission_rules(self, parent, o):
        d = dialog(parent, 'Zasady rekrutacji', f"{o['name']} · {o['degree_label']} · {o['mode_label']}", 770, accent=o['color'])
        fees, terms = card(16)
        terms.addWidget(label('Opłaty w tej edycji', 18, NAVY, True))
        amounts = box(horizontal=True)
        entries = [('Opłata rekrutacyjna', o['fee'])]
        if o['tuition_per_semester'] is not None:
            entries.append(('Czesne za semestr', o['tuition_per_semester']))
        for title, value in entries:
            col = box(spacing=3)
            col.addWidget(label(title, 12, MUTED, wrap=True))
            col.addWidget(label(f"{value.replace('.', ',')} zł", 21, NAVY, True))
            amounts.addLayout(col, 1)
        terms.addLayout(amounts)
        d.form.addWidget(fees)
        score, factors = card(16)
        factors.addWidget(label('Jak powstaje ranking?', 18, NAVY, True))
        if o['degree'] == 'I':
            factors.addWidget(wr_formula())
            for text in ['M – matematyka na poziomie podstawowym',
                         'P₁, P₂ – wyniki z dwóch dopuszczonych przedmiotów lub kwalifikacji',
                         'D – premia za udokumentowane osiągnięcie']:
                factors.addWidget(label(text, 13, MUTED, wrap=True))
        elif o['degree'] == 'II':
            factors.addWidget(label('W rankingu liczy się średnia ze studiów I stopnia.', 15, NAVY, True, True))
        else:
            factors.addWidget(label('Zgłoszenia z dyplomem są porządkowane według kolejności złożenia.', 15, NAVY, True, True))
        d.form.addWidget(score)
        evidence, required = card(16)
        required.addWidget(label('Przedmioty i dokumenty' if o['degree'] == 'I' else 'Dokumenty', 18, NAVY, True))
        if o['degree'] == 'I':
            for title, items in [('Dopuszczone rozszerzenia', o['subjects']), ('Kwalifikacje technika', o['professions'])]:
                if items:
                    required.addWidget(label(title, 13, NAVY, True))
                    required.addWidget(label(' · '.join(items), 13, MUTED, wrap=True))
            required.addWidget(label('Do profilu dodaj świadectwo maturalne.', 13, MUTED, wrap=True))
        else:
            required.addWidget(label('Do profilu dodaj dyplom ukończenia studiów.', 13, MUTED, wrap=True))
        if o['portfolio_required']:
            required.addWidget(label('Portfolio jest wymagane.', 13, NAVY, True))
        if o['portfolio_bonus']:
            required.addWidget(label('Wyróżnione portfolio podnosi P₂ do 100.', 13, MUTED))
        d.form.addWidget(evidence)
        d.buttons.insertWidget(1, website('Oficjalne opłaty PK', FEES_URL))
        d.resize(770, 760)
        d.exec()
