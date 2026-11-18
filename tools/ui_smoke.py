"""Render actual Qt windows against the running local API for visual inspection."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from datetime import date
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton, QTableWidget, QWidget
from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QFontDatabase
from admissions.campus import WELCOME_NOTIFICATION, WELCOME_OATH_INSTRUCTION
from desktop.app import MainWindow
from desktop.client import Client
from desktop.dashboard import CampusSlideshow
from desktop.widgets import PAGE_BACKGROUND, RowDelegate
from desktop.discover import FACULTY_IMAGES, PhotoHero
from desktop.housing_ui import CampusMap
from desktop.krakow import PlacePhoto
from desktop.lecturers import LecturerExplorer
from desktop.programme_marks import ProgrammeMark
from desktop.offer_form import OfferTerms
from desktop.overview_map import OverviewView
from portable import ROOT, config

app = QApplication([])
app.setStyle('Fusion')
for filename in ['segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf']:
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + filename)
client = Client(os.environ.get('PK_TEST_API','http://127.0.0.1:58421/api'),verify=os.environ.get('PK_TEST_CA') or True)
window = MainWindow(client, config()['demo_password'])
window.sync_timer.stop()
window.show()
out = Path(os.environ.get('PK_TEST_SCREENSHOTS', str(ROOT / 'tmp' / 'screenshots')))
out.mkdir(parents=True, exist_ok=True)

def capture(name):
    deadline = time.monotonic() + .45
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert window.grab().save(str(out / (name + '.png')))


def wait_for_refresh():
    deadline = time.monotonic() + 15
    while window.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.02)
    assert not window.busy, 'GUI hung while refreshing data.'

def sign_in(role):
    client.token = json.loads(os.environ.get('PK_TEST_TOKENS', '{}')).get(role, '')
    if not client.token:
        result = client.request('/login', {'email': role + '@demo.local', 'password': config()['demo_password']})
        client.token = result['token']
    window.data = client.request('/workspace')
    window.sync_revision = window.data['revision']
    window.offers = client.request('/catalog')
    window.threshold_rows = client.request('/thresholds')
    window.current = 'dashboard'
    window.shell()


def label_named(container, name):
    return next(item for item in container.findChildren(QLabel) if item.text() == name)


def origin(widget):
    return widget.mapToGlobal(QPoint())


def modal_capture(name, method, inspect=None, prepare=None):
    errors = []

    def setup():
        try:
            prepare(app.activeModalWidget())
        except Exception as error:
            errors.append(error)

    def shoot():
        modal = app.activeModalWidget()
        try:
            assert modal
            if inspect:
                inspect(modal)
            app.processEvents()
            assert modal.grab().save(str(out / (name + '.png')))
        except Exception as error:
            errors.append(error)
        finally:
            if modal:
                modal.reject()

    if prepare:
        QTimer.singleShot(150, setup)
    QTimer.singleShot(1800, shoot)
    method()
    if errors:
        raise errors[0]


def check_entry_frame(page):
    opened = []

    class WindowObserver(QObject):
        def eventFilter(self, widget, event):
            if event.type() == QEvent.Type.Show and isinstance(widget, QWidget) and widget.isWindow():
                opened.append(widget.metaObject().className())
            return False

    observer = WindowObserver()
    app.installEventFilter(observer)
    try:
        window.navigate(page)
        transition = window.page_transition
        assert transition.isVisible()
        transition.animation.pause()
        app.processEvents()
        assert not opened, (page, opened)
        assert transition.incoming.toImage() == transition.capture(window.page).toImage(), page
        transition.animation.resume()
    finally:
        app.removeEventFilter(observer)


def check_hero_layout():
    hero = window.page.findChild(PhotoHero)
    for heading in hero.panel.findChildren(QLabel):
        assert heading.height() >= heading.heightForWidth(heading.width())
        assert hero.panel.rect().contains(heading.geometry())
    for action in hero.panel.findChildren(QPushButton):
        assert action.height() >= action.minimumSizeHint().height()
        assert hero.panel.rect().contains(action.geometry())
    return hero.height()


def dashboard_layout():
    left = label_named(window.page, 'Twój następny krok').parentWidget()
    right = label_named(window.page, 'Terminy i sprawy studenckie').parentWidget()
    assert origin(left).y() == origin(right).y() and left.height() == right.height()
    carousel = window.page.findChild(CampusSlideshow)
    assert abs(carousel.stage.width() - carousel.stage.height() * 3) <= 2
    image_bottom = origin(carousel.stage).y() + carousel.stage.height()
    assert image_bottom < min(origin(carousel.caption).y(), origin(carousel.pause).y())
    media = label_named(window.page, 'Życie na Polibudzie').parentWidget()
    assert origin(carousel).y() == origin(media).y()
    assert origin(label_named(window.page, 'Przydatne na kampusie')).y() > origin(media).y()
    return carousel


stage = os.environ.get('PK_TEST_STAGE', 'open')
if stage == 'closed':
    sign_in('kandydat')
    assert any(w.text() == 'Kierunek uruchomiony' for w in window.page.findChildren(QLabel))
    assert window.nav_buttons['notifications'].unread > 0
    capture('kandydat-po-naborze')
    dashboard_layout()
    welcome = next(note for note in window.data['notifications'] if note['title'] == WELCOME_NOTIFICATION)
    assert WELCOME_OATH_INSTRUCTION in welcome['message']
    # Verify the desktop also shows the instruction for notices saved by an older version.
    welcome['message'] = welcome['message'].replace(WELCOME_OATH_INSTRUCTION + ' ', '')
    window.navigate('notifications')
    assert any(WELCOME_OATH_INSTRUCTION in item.text() for item in window.page.findChildren(QLabel))
    capture('kandydat-powiadomienie-slubowanie')
    window.navigate('housing')
    assert window.data['housing']['request']['status'] == 'awarded'
    capture('kandydat-przydzial-akademika')
    sign_in('komisja')
    window.navigate('housing')
    assert window.page.findChild(CampusMap).radius > 0
    capture('komisja-akademiki-wyniki')
    data = window.data['housing']
    for radius in (0.85, 18, 147.18):
        map_widget = CampusMap({**data, 'min_distance': radius}, overview=True)
        map_widget.resize(690, 348)
        map_widget.show()
        app.processEvents()
        area = QRectF(map_widget.rect()).adjusted(1, 1, -1, -1)
        view = OverviewView(area, data['campus'], radius)
        assert abs(view.scale * radius / area.height() - .33) < .001
        lat, lon = data['campus']
        point = view.project(lat + .1, lon) - view.origin
        assert abs(point.x()) < .001 and abs(-point.y() / view.scale - 11.119508) < .00001
        assert map_widget.grab().save(str(out / f'komisja-mapa-{radius:g}km.png'))
        map_widget.close()
    window.close()
    sys.exit(0)
if stage == 'sworn':
    sign_in('kandydat')
    candidate = next(a for a in window.data['applications'] if a['sworn_at'])

    def check_application(modal):
        welcome = label_named(modal, 'Gratulacje! Zaczynasz nowy rozdział.')
        preparation = label_named(modal, 'Przygotuj się do pierwszych zajęć')
        assert origin(welcome).y() < origin(preparation).y()
        identity = origin(label_named(modal, candidate['candidate']))
        documents = origin(label_named(modal, 'Dokumenty'))
        assert abs(documents.y() - identity.y()) <= 2 and documents.x() > identity.x()

    def check_card(modal):
        first, last = (date.fromisoformat(candidate[key]).strftime('%d.%m.%Y')
                       for key in ['card_valid_from', 'card_valid_until'])
        validity = label_named(modal, f'Ważność od {first} do {last}')
        viewport = modal.scroll.viewport()
        assert viewport.rect().contains(validity.mapTo(viewport, validity.rect().bottomLeft()))

    capture('kandydat-pulpit-po-slubowaniu')
    dashboard_layout()
    modal_capture('kandydat-po-slubowaniu', lambda: window.application_dialog(candidate), check_application)
    modal_capture('kandydat-legitymacja', lambda: window.student_card(candidate), check_card)
    window.close()
    sys.exit(0)
if stage == 'planning':
    sign_in('admin')
    window.navigate('catalog')
    assert any(w.text() == 'Dodaj ofertę studiów' for w in window.page.findChildren(QPushButton))
    capture('admin-planowanie-kierunkow')
    offer = next(o for o in window.offers if o['configurable'] and o['degree'] == 'I' and o['mode'] == 'N')
    errors = []

    def check_terms():
        modal = app.activeModalWidget()
        try:
            terms = modal.findChild(OfferTerms)
            assert terms.tuition.isVisible() and terms.tuition.text() == '3630.25'
            modal.scroll.ensureWidgetVisible(terms.fee)
            app.processEvents()
            assert modal.grab().save(str(out / 'admin-warunki-oferty.png'))
        except Exception as error:
            errors.append(error)
        finally:
            if modal:
                modal.reject()

    QTimer.singleShot(250, check_terms)
    window.offer_dialog(offer)
    if errors:
        raise errors[0]
    window.close()
    sys.exit(0)


capture('01-login')
assert not window.statusBar().isVisible()
about = next(item for item in window.findChildren(QPushButton) if item.text() == '© O aplikacji')
modal_capture('o-aplikacji', about.click, lambda modal: label_named(modal, '© Piotr Grodny i Marcin Gurdziel'))
assert len(set(FACULTY_IMAGES.values())) == 8
assert all((ROOT / 'assets' / name).is_file() for name in FACULTY_IMAGES.values())
window.guest()
wait_for_refresh()
capture('gosc-odkryj-pk')

assert 'lecturers' in window.nav_buttons
check_entry_frame('lecturers')
explorer=window.page.findChild(LecturerExplorer)
assert explorer and len(explorer.faculty_buttons)==8
assert len({selector.y() for _, selector in explorer.faculty_buttons}) == 1
for _, selector in explorer.faculty_buttons:
    assert selector.height() == 70
    assert selector.rect().contains(selector.findChild(ProgrammeMark).geometry())
capture('gosc-poznaj-wykladowcow')
navigation=window.findChild(QWidget,'navigation-menu')
navigation_image=navigation.grab().toImage()
assert navigation_image.pixelColor(navigation_image.width()-2,navigation_image.height()-2).name()=='#062b55'
previous_size = window.size()
window.resize(1280, 740)
app.processEvents()
scroll = window.page.verticalScrollBar()
assert scroll.maximum() > 0
scroll.setValue(min(scroll.maximum(), explorer.detail.mapTo(window.page.widget(), QPoint()).y() + 32))
app.processEvents()
explorer.findChild(QPushButton,'lecturer-michal').click()
scroll.setValue(0)
window.resize(previous_size)
capture('wykladowca-michal-jelen')
name = next(w for w in explorer.findChildren(QLabel,'lecturer-name') if w.isVisible())
assert name.text() == 'dr Michał Jeleń' and not name.visibleRegion().isEmpty()
selected = explorer.findChild(QPushButton, 'lecturer-michal')
selected.click()
assert selected.isChecked()
for faculty,selector in explorer.faculty_buttons:
    selector.click()
    app.processEvents()
    assert explorer.faculty==faculty['code'] and selector.isChecked()
    assert 2 <= len(explorer.map.buttons) <= 3
    for portrait in explorer.map.buttons:
        assert explorer.map.rect().contains(portrait.geometry())
window.navigate('discover')
window.page_transition.finish()
if stage=='open':
    from ui_document_checks import run as check_uploads
    check_uploads(app,window,out)
    wait_for_refresh()
    capture('gosc-po-tescie-dokumentow')
discover_height = check_hero_layout()
check_entry_frame('campus')
assert check_hero_layout() == discover_height == 244
capture('gosc-zycie-na-pk')
check_entry_frame('discover')
check_hero_layout()
window.navigate('krakow')
transition = window.page_transition
assert transition.isVisible() and window.pages.childAt(3, 3) is transition
transition.animation.pause()
transition.animation.setCurrentTime(transition.animation.duration() // 2)
app.processEvents()
frozen = window.pages.grab().toImage()
corner = frozen.pixelColor(3, 3)
assert corner.name() == PAGE_BACKGROUND.lower() and corner.alpha() == 255
left, right = frozen.width() // 4, frozen.width() * 3 // 4
sample_row = frozen.height() // 4
assert frozen.pixelColor(left, sample_row) == transition.incoming.toImage().pixelColor(left, sample_row)
assert frozen.pixelColor(right, sample_row) == transition.outgoing.toImage().pixelColor(right, sample_row)
old_style = window.page_body.styleSheet()
window.page_body.setStyleSheet('background:#000;')
app.processEvents()
assert window.pages.grab().toImage() == frozen
window.page_body.setStyleSheet(old_style)
assert window.grab().save(str(out / 'przejscie-w-polowie.png'))
window.navigate('discover')
assert transition.isVisible() and transition.incoming is not None
window.navigate('krakow')
capture('gosc-krakow')
assert not transition.isVisible() and 'krakow' in window.nav_buttons
photos = window.page.findChildren(PlacePhoto)
assert len(photos) == 6 and all(not photo.photo.isNull() for photo in photos)
window.page.verticalScrollBar().setValue(window.page.verticalScrollBar().maximum())
capture('gosc-krakow-spacery')
for role in ['kandydat', 'komisja', 'admin']:
    sign_in(role)
    assert 'lecturers' in window.nav_buttons
    if role == 'kandydat':
        window.navigate('catalog')
        app.processEvents()
    pages = (['dashboard', 'catalog', 'profile', 'timeline', 'housing', 'krakow'] if role == 'kandydat'
             else ['dashboard', 'ranking', 'housing', 'review'] if role == 'komisja' else ['dashboard', 'admin'])
    for page in pages:
        if page == 'dashboard' and role == 'kandydat':
            check_entry_frame(page)
            dashboard_layout()
        else:
            window.navigate(page)
        if page == 'housing' and role == 'kandydat':
            summary = window.page.findChild(QWidget, 'housing-residence-summary')
            assert label_named(summary, '4 domy studenckie')
            choice = next(w for w in window.page.findChildren(QPushButton) if w.text().startswith('DS2'))
            choice.click()
            assert choice.isChecked() and window.page.findChild(CampusMap).active == 'DS2'
        if page == 'ranking':
            search = next(w for w in window.page.findChildren(QLineEdit) if 'w rankingu' in w.accessibleName())
            search.setText('Informatyka')
            result_table = window.page.findChild(QTableWidget)
            assert 0 < result_table.rowCount() < len(window.offers)
        if page == 'profile':
            deadline = time.monotonic() + 5
            while not any(w.pixmap() and not w.pixmap().isNull() for w in window.page.findChildren(QLabel)):
                app.processEvents()
                assert time.monotonic() < deadline, 'Profile photo did not load.'
                time.sleep(.025)
        capture(role + '-' + page)
        if page == 'dashboard' and role == 'kandydat':
            carousel = dashboard_layout()
            assert carousel.stage.current == 0 and all(not image.isNull() for image in carousel.stage.images)
            carousel.pause.click()
            assert not carousel.timer.isActive()
            next(photo for photo in carousel.findChildren(QPushButton) if photo.accessibleName() == 'Następne zdjęcie').click()
            assert carousel.stage.current == 1
            if carousel.caption.text() != 'Kraków nad Wisłą':
                carousel.move(1)
            assert carousel.caption.text() == 'Kraków nad Wisłą'
            capture('kandydat-pulpit-panorama')
            carousel.move(1)
            assert carousel.caption.text() == 'Robotyka w praktyce'
            carousel.move(1)
            assert carousel.caption.text() == 'Zakrzówek' and 'Jakub Hałun' in carousel.credit.text()
            icons = {control.accessibleName() for control in window.page.findChildren(QPushButton) if not control.icon().isNull()}
            assert {'Facebook PK', 'Instagram PK', 'Spotify', 'YouTube'} <= icons
        if page == 'profile':
            buttons = window.page.findChildren(QPushButton)
            for _, title in window.data['profile']['document_kinds']:
                assert any(control.accessibleName().endswith(' ' + title) for control in buttons)
            assert any(control.accessibleName() == 'Adres do powiadomień (opcjonalny)' for control in window.page.findChildren(QLineEdit))
            for left, right in [('Dane kandydata', 'Adres zamieszkania'), ('Ukończone studia', 'Wyniki matury i kwalifikacje')]:
                a, b = (origin(label_named(window.page, name)) for name in (left, right))
                assert a.y() == b.y() and a.x() < b.x()
            result_rows = window.page.findChild(QTableWidget)
            total = result_rows.rowCount()
            assert total > 0
            result_rows.cellWidget(0, 3).click()
            assert result_rows.rowCount() == total - 1
        if page == 'review':
            item = window.page.findChild(QTableWidget).item(0, 2)
            assert int(item.textAlignment()) == int(Qt.AlignmentFlag.AlignCenter)
    if role=='komisja':
        assert not window.nav_buttons['ranking'].icon().isNull()
        candidate=next(a for a in window.data['applications'] if a['email']=='kandydat@demo.local')
        def verify_form(modal):
            buttons = [w for w in modal.findChildren(QPushButton) if w.text() in (
                'Zamknij','Do uzupełnienia','Odrzuć','Zatwierdź dokumenty i opłatę')]
            assert len(buttons) == 4 and len({w.y() for w in buttons}) == 1
            payment = next(w for w in modal.findChildren(QCheckBox) if w.text().startswith('Kwota na'))
            amount = next(w for w in modal.findChildren(QLineEdit) if w.accessibleName().startswith('Kwota odczytana'))
            amount.setText('50,00')
            payment.click()
            assert not amount.isEnabled() and not amount.text()
            assert any(w.text() == 'Punktacja kandydata' for w in modal.findChildren(QLabel))
            modal.scroll.ensureWidgetVisible(amount, 10, 70)
        modal_capture('commission-application',lambda:window.application_dialog(candidate),verify_form)
        def choose_ranking_row(modal):
            ranking = modal.findChild(QTableWidget)
            assert ranking.rowCount() > 10 and isinstance(ranking.itemDelegate(), RowDelegate)
            ranking.setCurrentCell(2, 1)
            ranking.setFocus()
        modal_capture('commission-ranking',lambda:window.ranking_dialog(next(o for o in window.offers if o['id']==candidate['offer_id'])),
                      choose_ranking_row)
        architecture = next(a for a in window.data['applications'] if a['name']=='Architektura' and a['status']=='submitted')
        def check_evidence(modal):
            for item in modal.findChildren(QCheckBox):
                item.setChecked(True)
        def batch_ready(modal):
            confirm = next(w for w in modal.findChildren(QPushButton) if w.text()=='Zatwierdź gotowe')
            assert confirm.isEnabled()
            assert modal.findChild(QTableWidget).rowCount() == 2
        modal_capture('commission-batch',lambda:window.batch_dialog('verify',[candidate['id'],architecture['id']]),
                      batch_ready,check_evidence)
        search = next(control for control in window.page.findChildren(QLineEdit) if control.placeholderText() == 'Kandydat lub kierunek…')
        status = next(control for control in window.page.findChildren(QComboBox) if control.accessibleName() == 'Status zgłoszenia')
        mode = next(control for control in window.page.findChildren(QComboBox) if control.accessibleName() == 'Tryb studiów')
        search.setText('Informatyka')
        status.setCurrentIndex(status.findData('submitted'))
        mode.setCurrentIndex(mode.findData('S'))
        window.refresh()
        wait_for_refresh()
        assert window.filters['review'] == {'search': 'Informatyka', 'status': 'submitted', 'mode': 'S'}
    if role == 'kandydat':
        window.navigate('catalog')
        window.page_transition.finish()
        varied = next(o for o in window.offers if o['name']=='Architektura' and o['degree']=='I' and o['mode']=='S')
        window.degree_filter.showPopup()
        app.processEvents()
        assert window.degree_filter.view().window().grab().save(str(out / 'filtr-katalogu.png'))
        window.degree_filter.hidePopup()
        window.search.setText('Architektura')
        assert window.grid.count() == len({o['program_id'] for o in window.visible_offers})
        assert len(window.visible_offers) > window.grid.count()
        window.mode_filter.setCurrentIndex(window.mode_filter.findData('N'))
        assert window.visible_offers and all(o['mode']=='N' for o in window.visible_offers)
        def select_mode(modal):
            chooser = next(w for w in modal.findChildren(QComboBox) if w.accessibleName() == 'Tryb studiów')
            assert chooser.count() == 2
            chooser.setCurrentText('Niestacjonarne')
            assert any('Czesne przykładowe' in w.text() for w in modal.findChildren(QLabel))
        modal_capture('candidate-offer',lambda:window.offer_dialog(varied),select_mode)
        modal_capture('candidate-rules', lambda: window.admission_rules(window, varied))
        window.search.clear()
        window.mode_filter.setCurrentIndex(0)
        window.degree_filter.setCurrentIndex(2)
        capture('kandydat-podyplomowe')
        window.resize(1280, 800)
        window.navigate('catalog')
        assert window.degree_filter.currentData() == 'PG'
        capture('kandydat-catalog-1280')
        window.resize(1440, 940)
    client.request('/action', {'action': 'logout'})
    client.token = ''
window.close()
print('Qt screens rendered:', len(list(out.glob('*.png'))), 'in', out)
