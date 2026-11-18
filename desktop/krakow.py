from functools import lru_cache
from html import escape
import json

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QGridLayout, QWidget

from portable import ROOT
from .discover import PhotoHero, website
from .photos import draw_cover
from .widgets import MUTED, NAVY, card, label


PHOTOS = ROOT / 'assets' / 'krakow'
TOURISM = 'https://www.krakow.pl/turystyka/264,glowna.html'
CITY_MAP = 'https://www.openstreetmap.org/#map=14/50.0564/19.9449'
PLACES = (
    ('Stare Miasto i Kazimierz', (
        ('rynek', 'Rynek Główny',
         'Zacznij od Sukiennic i bazyliki Mariackiej. Pod płytą placu muzeum pokazuje ślady średniowiecznego Krakowa.',
         'Rynek Podziemny', 'https://www.muzeumkrakowa.pl/oddzialy/rynek-podziemny'),
        ('wawel', 'Wzgórze Wawelskie',
         'Przejdź na dziedziniec Zamku Królewskiego, zajrzyj do katedry i zejdź w stronę Wisły.',
         'Zwiedzanie Wawelu', 'https://wawel.krakow.pl/zwiedzanie'),
        ('kazimierz', 'Kazimierz',
         'Przejdź od ulicy Szerokiej i Starej Synagogi do placu Nowego. Po drodze zobaczysz dawne synagogi i podwórka.',
         'Ulica Szeroka', 'https://www.krakow.pl/instcbi/11195,inst,4879,303,instcbi.html'),
    )),
    ('Nad wodą i z widokiem', (
        ('bulwary', 'Bulwary Wiślane',
         'Idź wzdłuż Wisły od Wawelu do kładki Bernatka. Na drugim brzegu możesz przedłużyć spacer przez Podgórze.',
         'Kładka Bernatka', 'https://www.krakow.pl/instcbi/243325/inst/163501/2572/Kladka-Ojca-Bernatka.html'),
        ('zakrzowek', 'Park Zakrzówek',
         'Ścieżki nad dawnym kamieniołomem prowadzą do punktów widokowych na wapienne ściany i turkusowy zalew.',
         'Park i kąpielisko', 'https://zis.krakow.pl/park-zakrzowek-akwen-z-kapieliskiem?parent=baza-obiektow-sportowych'),
        ('kopiec', 'Kopiec Krakusa',
         'Wejdź na kopiec w Podgórzu, żeby zobaczyć Stare Miasto i Wawel z południa.',
         'Kopiec na mapie', 'https://www.openstreetmap.org/?mlat=50.0387&mlon=19.9589#map=17/50.0387/19.9589'),
    )),
)


@lru_cache(maxsize=1)
def krakow_credits():
    return json.loads((PHOTOS / 'credits.json').read_text(encoding='utf-8'))


def photo_credit(photo):
    data = krakow_credits()[photo]
    item = label('', 10, MUTED, wrap=True)
    item.setTextFormat(Qt.TextFormat.RichText)
    item.setText(
        f'<a style="color:#53667E;" href="{escape(data["source"])}">{escape(data["author"])}</a>'
        f' · <a style="color:#53667E;" href="{escape(data["license_url"])}">{escape(data["license"])}</a>'
    )
    item.setOpenExternalLinks(True)
    item.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return item


class PlacePhoto(QWidget):
    def __init__(self, name, title):
        super().__init__()
        self.photo = QPixmap(str(PHOTOS / f'{name}.jpg'))
        self.setFixedHeight(146)
        self.setAccessibleName(f'Zdjęcie · {title}')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect())
        shape = QPainterPath()
        shape.addRoundedRect(area, 9, 9)
        painter.setClipPath(shape)
        painter.fillRect(area, QColor('#E3EBF5'))
        draw_cover(painter, area, self.photo)


def show_krakow(content):
    hero = PhotoHero('Poznaj Kraków', 'Od Rynku i Wawelu po spacery nad Wisłą i widok z Kopca Krakusa.',
                     'krakow/panorama.jpg', [website('Przewodnik miejski', TOURISM), website('Mapa miasta', CITY_MAP)],
                     height=260, accent='#147D69')
    source = hero.photo
    sky_margin = round(source.height() * .18)
    hero.photo = source.copy(0, sky_margin, round(source.width() * .53), source.height() - sky_margin)
    hero.setFixedHeight(260)
    content.addWidget(hero)
    content.addWidget(photo_credit('panorama'))
    for section, places in PLACES:
        content.addWidget(label(section, 21, NAVY, True))
        grid = QGridLayout()
        grid.setSpacing(16)
        for column, (file, title, description, action, url) in enumerate(places):
            panel, body = card(13)
            body.setSpacing(8)
            body.addWidget(PlacePhoto(file, title))
            body.addWidget(photo_credit(file))
            body.addWidget(label(title, 18, NAVY, True, True))
            body.addWidget(label(description, 13, MUTED, wrap=True))
            body.addStretch()
            link = website(action, url)
            link.setAccessibleName(f'{action} · {title}')
            body.addWidget(link)
            grid.setColumnStretch(column, 1)
            grid.addWidget(panel, 0, column)
        content.addLayout(grid)
    content.addStretch()
