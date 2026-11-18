from datetime import datetime
from html import escape
from pathlib import Path
import json
import os
import tempfile
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap, QIcon, QDesktopServices, QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QLineEdit,
    QDialog, QMessageBox, QFileDialog, QStackedWidget)
from admissions.campus import WELCOME_NOTIFICATION, WELCOME_OATH_INSTRUCTION
from admissions.version import VERSION
from .client import asynchronously
from .widgets import *
from .visuals import FacultyRibbon, FacultyHeader, status_chip
from portable import ROOT, DATA
from .pages import WorkspacePages
from .page_transition import PageTransition
from .flows import WorkflowPages
from .discover import DiscoveryPages
from .housing_ui import HousingPages
from .profile_forms import ProfilePages, address_fields

DEGREES = [('I stopień', 'I'), ('II stopień', 'II'), ('Podyplomowe', 'PG')]


def date(value):
    if not value:
        return '—'
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone().strftime('%d.%m.%Y, %H:%M')


class FormDialog(QDialog):
    def __init__(self, parent, title, subtitle='', width=660, accent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        screen = parent.screen()
        if screen:
            self.setMaximumHeight(min(850, screen.availableGeometry().height() - 72))
        self.resize(width, 450)
        outer = box(self, margins=24, spacing=16)
        if accent:
            outer.addWidget(FacultyHeader(title, subtitle, accent))
        else:
            outer.addWidget(label(title, 24, bold=True, wrap=True))
            if subtitle:
                outer.addWidget(label(subtitle, 13, MUTED, wrap=True))
        self.sync_banner = label('Stan naboru zmienił się na serwerze. Odśwież widok przed zapisem.', 12, '#996020', True, True)
        self.sync_banner.hide()
        outer.addWidget(self.sync_banner)
        self.scroll, self.body, self.form = scroll_page()
        self.form.setContentsMargins(0, 0, 8, 0)
        self.form.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addWidget(self.scroll, 1)
        self.actions = box(horizontal=True, spacing=8)
        outer.addLayout(self.actions)
        self.buttons = box(horizontal=True)
        self.buttons.addStretch()
        self.close_button = button('Zamknij', self.reject, secondary=True)
        self.buttons.addWidget(self.close_button)
        outer.addLayout(self.buttons)


class MainWindow(WorkflowPages, DiscoveryPages, WorkspacePages, ProfilePages, HousingPages, QMainWindow):
    def __init__(self, client, demo_password='', on_close=None, connection_info=None):
        super().__init__()
        self.client = client
        self.demo_password = demo_password
        self.on_close_callback = on_close
        self.data = {}
        self.offers = []
        self.threshold_rows = []
        self.tasks = []
        self.current = 'dashboard'
        self.busy = False
        self.filters = {}
        self.campaign_id = None
        self.photo_cache = {}
        self.sync_busy = False
        self.sync_revision = None
        self.connection_info = connection_info
        self.setWindowTitle('Rekrutacja PK')
        self.setWindowIcon(QIcon(str(ROOT / 'assets' / 'pk.ico')))
        self.resize(1440, 940)
        self.setMinimumSize(1120, 740)
        self.setStyleSheet(STYLE)
        self.statusBar().hide()
        self.login_screen()
        QShortcut(QKeySequence('F5'), self, activated=self.refresh)
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.poll_server)
        self.sync_timer.start(5000)

    def run(self, function, done, status='Zapisywanie…'):
        if self.busy:
            return
        self.busy = True
        self.statusBar().showMessage(status)
        def finish(value):
            self.busy = False
            self.statusBar().showMessage('Połączono z serwerem rekrutacji', 5000)
            done(value)
        def fail(error):
            self.busy = False
            self.statusBar().showMessage('Operacja nie została zakończona.', 8000)
            QMessageBox.warning(self, 'Sprawdź dane', error)
            if not self.client.token and self.data:
                self.reset_session()
        task = asynchronously(function, finish, fail)
        self.tasks.append(task)
        # QRunnable is owned by the pool. Keep only a bounded set of Python wrappers.
        self.tasks = self.tasks[-20:]

    def mutate(self, data, dialog=None, done=None):
        def finished(result):
            if dialog:
                dialog.accept()
            if done:
                done(result)
            self.refresh()
        self.run(lambda: self.client.request('/action', data), finished)

    def operation_status(self):
        status = label(self.statusBar().currentMessage(), 11, MUTED, wrap=True)
        status.setAccessibleName('Stan operacji')
        self.statusBar().messageChanged.connect(status.setText)
        return status

    def about(self):
        details = FormDialog(self, 'O aplikacji', f'Rekrutacja PK · wersja {VERSION}', width=490)
        details.form.addWidget(label('© Piotr Grodny i Marcin Gurdziel', 19, NAVY, True, True))
        details.form.addWidget(label('Rok akademicki 2026/2027 · semestr zimowy', 14, MUTED, wrap=True))
        details.form.addWidget(label('Projekt akademicki z przykładowymi danymi i terminami.', 13, MUTED, wrap=True))
        details.resize(490, 250)
        details.exec()

    def login_screen(self):
        self.current = 'login'
        root = QWidget()
        root.setObjectName('root')
        outer = box(root, horizontal=True, margins=40, spacing=0)
        intro = QFrame()
        intro.setObjectName('hero')
        left = box(intro, margins=48, spacing=22)
        symbol = QLabel()
        symbol.setPixmap(QPixmap(str(ROOT / 'assets' / 'pk.png')).scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        symbol.setStyleSheet('background: white; padding: 12px; border-radius: 14px;')
        symbol.setFixedSize(100, 100)
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(symbol)
        left.addWidget(label('POLITECHNIKA KRAKOWSKA', 12, '#BBD0E9', True))
        left.addWidget(FacultyRibbon(12))
        left.addStretch()
        left.addWidget(label('Twoja przyszłość.\nTwój kierunek.', 46, '#FFFFFF', True, True))
        left.addWidget(label('Wybierz studia, złóż dokumenty i śledź każdy etap swojej rekrutacji w jednym miejscu.', 18, '#C6D9EE', wrap=True))
        left.addWidget(Journey(['Wybierz kierunek', 'Złóż zgłoszenie', 'Potwierdź miejsce'], 0, True))
        left.addStretch()
        authors = button('© O aplikacji', self.about)
        authors.setStyleSheet('QPushButton { background:transparent; border-color:#7595B7; color:white; text-align:left; }')
        left.addWidget(authors, alignment=Qt.AlignmentFlag.AlignLeft)
        outer.addWidget(intro, 6)
        form_panel = QWidget()
        right = box(form_panel, margins=56, spacing=14)
        right.addStretch()
        right.addWidget(chip('REKRUTACJA NA STUDIA'))
        right.addWidget(label('Dobrze Cię widzieć', 30, bold=True))
        right.addWidget(label('Zaloguj się, aby przejść do swojego panelu.', 14, MUTED, wrap=True))
        email = field(right, 'Adres e-mail', placeholder='twoj.adres@example.com')
        password = field(right, 'Hasło', secret=True)
        code = field(right, 'Kod dwuetapowy, jeśli włączony', placeholder='6 cyfr z aplikacji uwierzytelniającej')
        code.setMaxLength(6)
        def perform():
            payload = {'email': email.text(), 'password': password.text(), 'code': code.text()}
            self.run(lambda: self.client.request('/login', payload), self.logged_in, 'Logowanie…')
        right.addWidget(button('Zaloguj się  →', perform))
        password.returnPressed.connect(perform)
        code.returnPressed.connect(perform)
        links = box(horizontal=True)
        links.addWidget(button('Utwórz konto', self.registration, secondary=True))
        links.addWidget(button('Odzyskaj dostęp', self.recovery, secondary=True))
        right.addLayout(links)
        right.addSpacing(12)
        demo_label = label('KONTA PRZYKŁADOWE', 10, MUTED, True)
        demo_label.setVisible(bool(self.demo_password))
        right.addWidget(demo_label)
        demo = combo([('Wybierz konto…', ''), ('Anna • kandydatka', 'kandydat'),
                      ('Michał • przyjęcie i ślubowanie', 'przyjety'), ('Klara • lista rezerwowa', 'rezerwa'),
                      ('Jan • odrzucony wniosek', 'odrzucony'), ('Oskar • brak potwierdzenia', 'bezpotwierdzenia'),
                      ('Maria • komisja', 'komisja'), ('Administrator', 'admin')], 'Konto przykładowe')
        def choose_demo():
            if demo.currentData():
                email.setText(demo.currentData() + '@demo.local')
                password.setText(self.demo_password)
                code.clear()
        demo.currentIndexChanged.connect(choose_demo)
        right.addWidget(demo)
        demo.setVisible(bool(self.demo_password))
        right.addWidget(button('Poznaj Politechnikę bez logowania', self.guest, secondary=True))
        right.addWidget(label('Projekt akademicki. Dane i terminy w kontach przykładowych są fikcyjne.', 11, MUTED, wrap=True))
        right.addWidget(self.operation_status())
        right.addStretch()
        outer.addWidget(form_panel, 5)
        self.setCentralWidget(root)

    def logged_in(self, result):
        self.client.token = result['token']
        if result.get('recovery_code'):
            self.show_recovery(result['recovery_code'])
        self.current = 'dashboard'
        self.refresh()

    def show_recovery(self, code):
        dialog = FormDialog(self, 'Zapisz kod odzyskiwania', 'Ten jednorazowy kod pozwoli odzyskać konto bez poczty i wyłączyć utracone uwierzytelnianie dwuetapowe.')
        entry = field(dialog.form, 'Kod odzyskiwania', code)
        entry.setReadOnly(True)
        dialog.form.addWidget(button('Kopiuj kod', lambda: QApplication.clipboard().setText(code), secondary=True))
        dialog.form.addWidget(label('Zachowaj go poza aplikacją. Kolejne odzyskanie dostępu utworzy nowy kod.', 13, MUTED, wrap=True))
        dialog.exec()

    def registration(self):
        d = FormDialog(self, 'Utwórz konto kandydata', 'Podaj dane identyfikacyjne i kontaktowe potrzebne komisji.', width=730)
        inputs = {k: field(d.form, title, secret=k == 'password') for k, title in
                  [('first_name', 'Imię'), ('last_name', 'Nazwisko'), ('email', 'Adres e-mail do logowania'),
                   ('notification_email', 'Adres e-mail do powiadomień (opcjonalnie)'),
                   ('password', 'Hasło (minimum 10 znaków)'), ('pesel', 'PESEL'), ('phone', 'Telefon kontaktowy')]}
        inputs['pesel'].setMaxLength(11)
        address = address_fields(d.form)
        def create():
            payload = {k: v.text() for k, v in inputs.items()}
            payload['address'] = {key: entry.text() for key, entry in address.items()}
            def done(result):
                d.accept()
                self.logged_in(result)
            self.run(lambda: self.client.request('/register', payload), done, 'Tworzenie konta…')
        d.buttons.addWidget(button('Utwórz konto', create))
        d.resize(730, 790)
        d.exec()

    def recovery(self):
        d = FormDialog(self, 'Odzyskaj dostęp', 'Podaj kod zapisany przy rejestracji lub włączeniu weryfikacji dwuetapowej.')
        inputs = {k: field(d.form, title, secret=k == 'password') for k, title in
                  [('email', 'Adres e-mail'), ('recovery_code', 'Kod odzyskiwania'), ('password', 'Nowe hasło') ]}
        def recover():
            def done(result):
                d.accept()
                self.show_recovery(result['recovery_code'])
            self.run(lambda: self.client.request('/recover', {k: v.text() for k, v in inputs.items()}), done)
        d.buttons.addWidget(button('Zmień hasło', recover))
        d.exec()

    def guest(self):
        self.current = 'discover'
        self.data = {'user': {'role': 'guest', 'first_name': 'Gość', 'last_name': '', 'email': '', 'role_label': 'Gość'}, 'applications': [], 'notifications': []}
        self.refresh()


    @property
    def role(self):
        return self.data.get('user', {}).get('role', 'guest')

    def shell(self):
        root = QWidget()
        root.setObjectName('root')
        layout = box(root, horizontal=True, spacing=0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(234)
        nav = box(sidebar, margins=16, spacing=5)
        brand = box(horizontal=True, spacing=12)
        icon = QLabel()
        icon.setPixmap(QPixmap(str(ROOT / 'assets' / 'pk.png')).scaled(36, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        icon.setStyleSheet('background:white; border-radius:7px; padding:7px;')
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(58, 58)
        brand.addWidget(icon)
        brand.addWidget(label('Rekrutacja PK\nPanel rekrutacyjny', 13, 'white', True))
        nav.addLayout(brand)
        nav.addSpacing(14)
        nav.addWidget(label('TWOJA PRZESTRZEŃ', 10, '#90AAC8', True))
        entries = [('dashboard', '◈   Pulpit'), ('catalog', '▦   Kierunki studiów'), ('applications', '▤   Moje zgłoszenia'),
                   ('timeline', '◷   Harmonogram'), ('thresholds', '≡   Progi rekrutacyjne'),
                   ('profile', '○   Mój profil'), ('housing', 'Akademiki'), ('notifications', '◇   Powiadomienia'),
                   ('discover', 'Odkryj PK'), ('lecturers', 'Poznaj wykładowców'),
                   ('campus', 'Życie na PK'), ('krakow', 'Poznaj Kraków')]
        if self.role in ['commission', 'admin']:
            entries = [('dashboard', '◈   Pulpit'), ('review', '▤   Weryfikacja zgłoszeń'), ('catalog', '▦   Kierunki i listy'),
                       ('ranking', '≡   Ranking na żywo'),
                       ('timeline', '◷   Harmonogram'), ('thresholds', '≡   Progi rekrutacyjne'), ('housing', 'Akademiki')]
        if self.role == 'admin':
            entries.append(('admin', '⚙   Administracja'))
        if self.role == 'guest':
            entries = [('discover', 'Odkryj PK'), ('catalog', 'Kierunki studiów'), ('campus', 'Życie na PK'),
                       ('lecturers', 'Poznaj wykładowców'), ('krakow', 'Poznaj Kraków'), ('thresholds', 'Progi rekrutacyjne')]
        if self.role in ['commission','admin']:
            entries.append(('lecturers', 'Poznaj wykładowców'))
        self.nav_buttons = {}
        menu_host = QWidget()
        menu_host.setObjectName('navigation-menu')
        menu_host.setStyleSheet('QWidget#navigation-menu { background:#062B55; }')
        menu = box(menu_host, margins=0, spacing=5)
        for key, title in entries:
            unread = self.data.get('unread_notifications', 0) if key == 'notifications' else 0
            btn = NavigationButton(key, title.split('   ', 1)[-1], lambda checked=False, k=key: self.navigate(k), unread)
            btn.setProperty('active', self.current == key)
            self.nav_buttons[key] = btn
            menu.addWidget(btn)
        menu.addStretch()
        menu_scroll = QScrollArea()
        menu_scroll.setObjectName('navigation-scroll')
        menu_scroll.viewport().setObjectName('navigation-viewport')
        menu_scroll.viewport().setStyleSheet('QWidget#navigation-viewport { background:#062B55; }')
        menu_scroll.setWidgetResizable(True)
        menu_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        menu_scroll.setWidget(menu_host)
        menu_scroll.setStyleSheet('QScrollArea#navigation-scroll { border:none; background:#062B55; } '
                                 'QScrollBar:vertical { background:#062B55; width:5px; } '
                                 'QScrollBar::handle:vertical { background:#47698B; }')
        nav.addWidget(menu_scroll,1)
        if 'campaign' in self.data:
            nav.addWidget(label('CZAS NABORU', 9, '#90AAC8', True))
            nav.addWidget(label(date(self.data['campaign']['now']), 12, '#D8E4F3'))
        nav.addSpacing(10)
        user = self.data['user']
        nav.addWidget(label(f"{user['first_name']} {user['last_name']}".strip(), 14, '#FFFFFF', True, True))
        if self.role != 'guest':
            nav.addWidget(label(user['role_label'], 11, '#AFC5DE'))
            security = button('Ustawienia bezpieczeństwa', self.security)
            security.setProperty('nav', True)
            nav.addWidget(security)
        out = button('←   Wyloguj' if self.role != 'guest' else '←   Logowanie', self.logout)
        out.setProperty('nav', True)
        nav.addWidget(out)
        layout.addWidget(sidebar)
        right = QWidget()
        body = box(right, spacing=0)
        topbar = QFrame()
        topbar.setObjectName('topbar')
        top = box(topbar, horizontal=True, margins=18)
        heading = box(spacing=3)
        heading.addWidget(label('SYSTEM REKRUTACJI', 11, MUTED, True))
        operation = self.operation_status()
        operation.setFixedHeight(2 * operation.fontMetrics().lineSpacing())
        operation.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        heading.addWidget(operation)
        top.addLayout(heading)
        top.addStretch()
        if self.data.get('campaigns'):
            editions = combo([(c['name'].removesuffix(' • demonstracja') + (' • archiwum' if c['closed'] else ''), c['id'])
                              for c in self.data['campaigns']])
            editions.setMaximumWidth(390)
            editions.setCurrentIndex(max(0, editions.findData(self.data['campaign']['id'])))
            def change_edition():
                selected = editions.currentData()
                self.campaign_id = None if selected == self.data['campaigns'][0]['id'] else selected
                self.filters = {}
                self.refresh()
            editions.currentIndexChanged.connect(change_edition)
            top.addWidget(editions)
        refresh_button = button('Odśwież', self.refresh, secondary=True)
        refresh_button.setIcon(line_icon('refresh', NAVY))
        top.addWidget(refresh_button)
        top.addWidget(button('© O aplikacji', self.about, secondary=True))
        body.addWidget(topbar)
        body.addWidget(FacultyRibbon(10))
        self.sync_notice = label('', 12, '#A56A16', True, True)
        self.sync_notice.setContentsMargins(24, 5, 24, 5)
        self.sync_notice.hide()
        body.addWidget(self.sync_notice)
        self.pages = QStackedWidget()
        self.page_transition = PageTransition(self.pages)
        body.addWidget(self.pages, 1)
        layout.addWidget(right, 1)
        self.setCentralWidget(root)
        self.navigate(self.current)

    def navigate(self, key):
        previous = self.pages.currentWidget()
        animate = (previous is not None and self.pages.isVisible() and key != self.current
                   and os.environ.get('PK_REDUCE_MOTION') != '1')
        if animate:
            self.page_transition.cover(previous)
        else:
            self.page_transition.finish()
        self.current = key
        for name, btn in self.nav_buttons.items():
            btn.setProperty('active', name == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.page, self.page_body, self.content = scroll_page()
        handler = getattr(self, 'page_' + key, self.page_dashboard)
        handler()
        self.pages.addWidget(self.page)
        self.pages.setCurrentWidget(self.page)
        if previous is not None:
            self.pages.removeWidget(previous)
            previous.deleteLater()
        if animate:
            self.page_transition.raise_()
            self.page_transition.reveal(self.page)

    def title(self, title, description):
        self.content.addWidget(label(title, 30, bold=True))
        self.content.addWidget(label(description, 14, MUTED, wrap=True))





    def page_applications(self):
        self.title('Moje zgłoszenia', 'Każdy kierunek ma własne dokumenty, opłatę i wynik. Zapisany szkic możesz uzupełnić później.')
        apps = self.data['applications']
        if not apps:
            f, l = card(32)
            l.addWidget(label('Tutaj zacznie się Twoja rekrutacja', 23, bold=True))
            l.addWidget(label('Wybierz kierunek, a następnie utwórz pierwsze zgłoszenie.', 14, MUTED))
            l.addWidget(button('Przeglądaj kierunki', lambda: self.navigate('catalog')))
            self.content.addWidget(f)
        for a in apps:
            f, l = card()
            row = box(horizontal=True)
            col = box()
            col.addWidget(label(a['name'], 20, bold=True, wrap=True))
            col.addWidget(label(f"{a['degree']} • {a['mode']} • tura {a['round']}", 12, MUTED))
            row.addLayout(col, 1)
            row.addWidget(status_chip(a['status'], a['status_label']))
            row.addWidget(button('Otwórz  →', lambda checked=False, app=a: self.application_dialog(app), secondary=True))
            l.addLayout(row)
            if a.get('sworn_at'):
                l.addWidget(label('Gratulacje! Ślubowanie zapisane — możesz obejrzeć legitymację.', 14, '#147D69', True, True))
                l.addWidget(button('Podgląd legitymacji', lambda checked=False, item=a: self.student_card(item), secondary=True))
            elif a.get('can_oath'):
                l.addWidget(label('Nabór zakończony. Otwórz zgłoszenie i złóż ślubowanie.', 14, '#147D69', True, True))
            if a['feedback']:
                l.addWidget(label(a['feedback'], 13, '#996020', wrap=True))
            offer = next(o for o in self.offers if o['id'] == a['offer_id'])
            if offer['threatened']:
                l.addWidget(label(f"Ryzyko nieuruchomienia: potwierdzono {offer['confirmed']} z minimum {offer['minimum']} miejsc. Możesz dodać zgłoszenie na inny kierunek w otwartej turze.", 13, '#996020', True, True))
                l.addWidget(button('Sprawdź alternatywne kierunki', lambda: self.navigate('catalog'), secondary=True))
            self.content.addWidget(f)
        self.content.addStretch()



    def page_thresholds(self):
        self.title('Progi rekrutacyjne', 'Wyniki po zamknięciu list. „-” oznacza brak publikacji. Studia II stopnia mają próg średniej, a podyplomowe kolejność zgłoszeń.')
        filters = box(horizontal=True)
        degree = combo(DEGREES)
        mode = combo([('Wszystkie tryby', ''), ('Stacjonarne', 'S'), ('Niestacjonarne', 'N')])
        saved = self.filters.get('thresholds', {})
        degree.setCurrentIndex(max(0, degree.findData(saved.get('degree'))))
        mode.setCurrentIndex(max(0, mode.findData(saved.get('mode'))))
        filters.addWidget(degree)
        filters.addWidget(mode)
        filters.addStretch()
        self.content.addLayout(filters)
        container = QWidget()
        layout = box(container)
        self.content.addWidget(container, 1)
        def render():
            self.filters['thresholds'] = {'degree': degree.currentData(), 'mode': mode.currentData()}
            while layout.count():
                layout.takeAt(0).widget().deleteLater()
            rows = [r for r in self.threshold_rows if r['degree'] == degree.currentData() and (not mode.currentData() or mode.currentData() == r['mode'])]
            count = 3 if degree.currentData() == 'I' else 2
            values = [[r['name'], r['faculty'], 'Stacj.' if r['mode'] == 'S' else 'Niestacj.'] + [v['label'] for v in r['values']] for r in rows]
            t = table(['Kierunek', 'Wydział', 'Tryb'] + [f'Tura {n}' for n in range(1, count + 1)], values)
            t.setMinimumHeight(550)
            layout.addWidget(t)
        degree.currentIndexChanged.connect(render)
        mode.currentIndexChanged.connect(render)
        render()


    def page_notifications(self):
        self.title('Powiadomienia', 'Decyzje komisji, wyniki i przypomnienia dotyczące Twoich zgłoszeń.')
        if self.data['notifications']:
            self.content.addWidget(button('Oznacz wszystkie jako przeczytane', lambda: self.mutate({'action': 'read_notifications'}), secondary=True))
        else:
            self.content.addWidget(label('Nie masz nowych powiadomień.', 15, MUTED))
        for n in self.data['notifications']:
            f, l = card()
            l.addWidget(label(('• ' if not n['read'] else '') + n['title'], 18, NAVY, True))
            text = n['message']
            if n['title'] == WELCOME_NOTIFICATION and WELCOME_OATH_INSTRUCTION not in text:
                text += f' {WELCOME_OATH_INSTRUCTION}'
            message = label(text, 14, MUTED, wrap=True)
            if n['title'] in [WELCOME_NOTIFICATION, 'Wynik wniosku o akademik']:
                from admissions.campus import ACCOUNTS, ADAPCIAK, DELTA, DEPARTMENT_PLANS, HOUSING_FEES, HOUSING_URL, SCHEDULES
                trusted = {ACCOUNTS: 'Instrukcja PK', ADAPCIAK: 'Informacje o Adapciaku', DELTA: 'Delta PK',
                           HOUSING_URL: 'Osiedle Studenckie', HOUSING_FEES: 'Cennik akademików',
                           SCHEDULES: 'Informacje dla studentów', **{url: 'Plan zajęć wydziału' for url in DEPARTMENT_PLANS.values()}}
                rendered = ' '.join(f'<a href="{escape(word)}">{escape(trusted[word])}</a>' if word in trusted else escape(word)
                                    for word in text.split())
                message.setTextFormat(Qt.TextFormat.RichText)
                message.setText(rendered)
                message.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
                message.setOpenExternalLinks(True)
            l.addWidget(message)
            l.addWidget(label(date(n['created_at']), 11, MUTED))
            self.content.addWidget(f)
        self.content.addStretch()



    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Zapisz listę przyjętych', 'przyjeci.csv', 'CSV (*.csv)')
        if path:
            self.run(lambda: self.client.request('/export' + self.campaign_query(), binary=True), lambda data: Path(path).write_bytes(data), 'Przygotowanie eksportu…')

    def backup(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Zapisz kopię bazy i dokumentów', 'rekrutacja-kopia.zip', 'Archiwum ZIP (*.zip)')
        if path:
            self.run(lambda: self.client.request('/backup', {}, binary=True), lambda data: (Path(path).write_bytes(data), QMessageBox.information(self, 'Kopia zapisana', 'Kopia zawiera bazę PostgreSQL, dokumenty i sumy kontrolne. Instrukcja odtworzenia znajduje się w README.')), 'Tworzenie kopii bazy i dokumentów…')

    def publication_dialog(self, offer):
        def show(data):
            d = FormDialog(self, 'Opublikowane listy • ' + offer['name'], 'Każda wersja pozostaje w historii. Zmiana wyniku tworzy nową publikację.', 930)
            if not data:
                d.form.addWidget(label('Brak opublikowanej listy.', 15, MUTED))
            for publication in data:
                d.form.addWidget(label(f"Tura {publication['round']} • wersja {publication['version']} • {date(publication['published_at'])}", 17, NAVY, True))
                rows = publication['entries']
                t = table(['Miejsce', 'Kandydat', 'Wynik', 'Decyzja'], [[e['rank'], e['candidate'], e['score'] or 'kolejność', 'Zakwalifikowano' if e['decision'] == 'qualified' else 'Rezerwa'] for e in rows], 1)
                t.setMinimumHeight(min(480, 70 + 48 * len(rows)))
                d.form.addWidget(t)
                if publication['reason']:
                    d.form.addWidget(label(publication['reason'], 13, MUTED, wrap=True))
            d.resize(930, 760)
            d.exec()
        self.run(lambda: self.client.request(f"/publications/{offer['id']}"), show, 'Pobieranie list…')


    def correction_dialog(self, app):
        d = FormDialog(self, 'Korekta opublikowanego wyniku', 'Zachowujemy poprzednią wersję. Zmiana przeliczy całą listę tej oferty w bieżącej turze i powiadomi kandydatów.')
        keys = ['M', 'P1', 'P2'] if app['degree'] == 'I' else ['average']
        fields = {k: field(d.form, k if k != 'average' else 'Średnia I stopnia', app['input'].get(k, '')) for k in keys}
        reason = field(d.form, 'Uzasadnienie i podstawa korekty')
        d.buttons.addWidget(button('Opublikuj nową wersję', lambda: self.mutate({'action': 'publish', 'offer_id': app['offer_id'], 'reason': reason.text(), 'correction': {'application_id': app['id'], **{k: v.text().replace(',', '.') for k, v in fields.items()}}}, d)))
        d.exec()

    def logout(self):
        if self.client.token:
            self.run(lambda: self.client.request('/action', {'action': 'logout'}), self.reset_session)
        else:
            self.reset_session()

    def reset_session(self, result=None):
        self.client.token = ''
        self.data = {}
        self.filters = {}
        self.campaign_id = None
        self.photo_cache.clear()
        self.login_screen()

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(self, 'Trwa operacja', 'Poczekaj na zakończenie bieżącej operacji przed zamknięciem programu.')
            event.ignore()
            return
        event.accept()
