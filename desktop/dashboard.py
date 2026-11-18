import os

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QTimer, QUrl, QVariantAnimation
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QSizePolicy, QWidget

from admissions.campus import FACEBOOK, INSTAGRAM, PK_MEDIA, PODCAST, PODCAST_SPOTIFY, RADIO
from portable import ROOT
from .discover import website
from .krakow import krakow_credits
from .photos import draw_cover
from .pk_content import CAMPUS_MAP
from .widgets import MUTED, NAVY, box, button, card, label


CAMPAIGN_SLIDE = ('kampania-studiuj-na-polibudzie.png', 'Kampania #StudiujNaPolibudzie',
                  'Materiały kampanii Politechniki Krakowskiej')
SLIDES = (
    ('kampus-pk.jpg', 'Kampus przy ul. Warszawskiej', 'Politechnika Krakowska · CC0 1.0'),
    ('krakow/panorama.jpg', 'Kraków nad Wisłą', ''),
    ('robotyka.jpg', 'Robotyka w praktyce', 'Nenad Stojković · CC BY 2.0'),
    ('krakow/zakrzowek.jpg', 'Zakrzówek', ''),
)
if (ROOT / 'assets' / CAMPAIGN_SLIDE[0]).is_file():
    SLIDES = (CAMPAIGN_SLIDE, *SLIDES)
BRAND_COLORS = {'facebook': '#1861CA', 'instagram': '#99448B', 'spotify': '#137C47', 'youtube': '#C62430'}


class PhotoStage(QWidget):
    def __init__(self):
        super().__init__()
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.images = [QPixmap(str(ROOT / 'assets' / name)) for name, *_ in SLIDES]
        self.current = self.previous = 0
        self.progress = 1.
        self.animation = QVariantAnimation(self, duration=320, easingCurve=QEasingCurve.Type.InOutQuad)
        self.animation.setStartValue(0.)
        self.animation.setEndValue(1.)
        self.animation.valueChanged.connect(self.set_progress)
        self.setAccessibleName(SLIDES[0][1])

    def sizeHint(self):
        return QSize(540, 180)

    def heightForWidth(self, width):
        return round(width / 3)

    def set_progress(self, value):
        self.progress = value
        self.update()

    def select(self, index, animate):
        self.animation.stop()
        self.previous, self.current = self.current, index
        self.setAccessibleName(SLIDES[index][1])
        self.set_progress(0. if animate else 1.)
        if animate:
            self.animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(area, 11, 11)
        painter.setClipPath(clip)

        painter.fillRect(area, QColor('#E3EBF5'))
        if self.progress < 1.:
            self.draw_slide(painter, area, self.previous)
            painter.setOpacity(self.progress)
        self.draw_slide(painter, area, self.current)

    def draw_slide(self, painter, area, index):
        photo = self.images[index]
        slide_path = SLIDES[index][0]
        if slide_path == CAMPAIGN_SLIDE[0] and not photo.isNull():
            painter.drawPixmap(area, photo, QRectF(photo.rect()))
        else:
            draw_cover(painter, area, photo, horizontal_focus=.18 if slide_path == 'krakow/panorama.jpg' else .5)


class CampusSlideshow(QFrame):
    def __init__(self, open_krakow):
        super().__init__()
        self.setObjectName('card')
        body = box(self, margins=16, spacing=9)
        heading = box(horizontal=True, spacing=8)
        heading.addWidget(label('Studiuj na Polibudzie', 19, NAVY, True, True), 1)
        explore = button('Poznaj Kraków →', open_krakow, secondary=True)
        explore.setStyleSheet('QPushButton { padding: 4px 10px; }')
        heading.addWidget(explore)
        body.addLayout(heading)
        self.stage = PhotoStage()
        body.addWidget(self.stage)
        row = box(horizontal=True, spacing=7)
        self.caption = label('', 12, NAVY, True, True)
        text = box(spacing=3)
        text.addWidget(self.caption)
        self.credit = label('', 10, MUTED, wrap=True)
        text.addWidget(self.credit)
        row.addLayout(text, 1)
        for title, accessible, direction in [('‹', 'Poprzednie zdjęcie', -1), ('›', 'Następne zdjęcie', 1)]:
            arrow = button(title, lambda _=False, step=direction: self.move(step), secondary=True)
            arrow.setAccessibleName(accessible)
            arrow.setFixedWidth(36)
            arrow.setStyleSheet('QPushButton { padding: 5px 6px; }')
            row.addWidget(arrow)
        self.animated = os.environ.get('PK_REDUCE_MOTION') != '1'
        self.timer = QTimer(self, interval=7500)
        self.timer.timeout.connect(lambda: self.move(1))
        self.pause = button('Wstrzymaj', self.toggle, secondary=True)
        if not self.animated:
            self.pause.hide()
        self.pause.setStyleSheet('QPushButton { padding: 5px 9px; }')
        row.addWidget(self.pause)
        body.addLayout(row)
        body.addStretch()
        self.update_caption(0)
        if self.animated:
            self.timer.start()

    def toggle(self):
        if self.timer.isActive():
            self.timer.stop()
            self.pause.setText('Wznów')
        else:
            self.timer.start()
            self.pause.setText('Wstrzymaj')

    def move(self, step):
        index = (self.stage.current + step) % len(SLIDES)
        self.stage.select(index, self.animated)
        self.update_caption(index)
        if self.timer.isActive():
            self.timer.start()

    def update_caption(self, index):
        path, title, credit = SLIDES[index]
        if path.startswith('krakow/'):
            photo = krakow_credits()[path.split('/')[1].removesuffix('.jpg')]
            credit = f"{photo['author']} · {photo['license']}"
        self.caption.setText(title)
        self.credit.setText(credit)


def brand_button(brand, name, url, *, icon_only=False):
    control = button('' if icon_only else name, lambda: QDesktopServices.openUrl(QUrl(url)))
    control.setIcon(QIcon(str(ROOT / 'assets' / 'brands' / f'{brand}.png')))
    control.setIconSize(QSize(18, 18))
    control.setAccessibleName(name)
    control.setToolTip(name)
    if icon_only:
        control.setFixedSize(39, 39)
    color = BRAND_COLORS[brand]
    control.setStyleSheet(
        f'QPushButton {{ background:{color}; border-color:{color}; padding:5px 10px; }}'
        'QPushButton:hover { background:#153A63; border-color:#153A63; }'
        'QPushButton:focus { border:2px solid #E3A832; }'
    )
    return control


def campus_resources():
    panel = QWidget()
    body = box(panel, spacing=14)
    media, links = card(15)
    links.setSpacing(8)
    links.addWidget(label('Życie na Polibudzie', 18, NAVY, True))
    links.addWidget(label('Podcast PK o studiach, ludziach i projektach.', 13, MUTED, wrap=True))
    listen = box(horizontal=True, spacing=7)
    listen.addWidget(brand_button('spotify', 'Spotify', PODCAST_SPOTIFY), 1)
    listen.addWidget(brand_button('youtube', 'YouTube', PODCAST), 1)
    links.addLayout(listen)
    profiles = box(horizontal=True, spacing=7)
    profiles.addWidget(brand_button('facebook', 'Facebook PK', FACEBOOK, icon_only=True))
    profiles.addWidget(brand_button('instagram', 'Instagram PK', INSTAGRAM, icon_only=True))
    profiles.addWidget(website('PK w mediach', PK_MEDIA), 1)
    profiles.addWidget(website('Radio Nowinki', RADIO), 1)
    links.addLayout(profiles)
    body.addWidget(media)

    campus, options = card(15)
    options.setSpacing(8)
    options.addWidget(label('Przydatne na kampusie', 17, NAVY, True))
    row = box(horizontal=True, spacing=7)
    row.addWidget(website('Mapa kampusów', CAMPUS_MAP), 1)
    row.addWidget(website('Biblioteka PK', 'https://www.biblos.pk.edu.pl/'), 1)
    options.addLayout(row)
    body.addWidget(campus, 1)
    return panel
