"""Offline maps of the student estate, Kraków and its region."""
from functools import lru_cache
import json
from math import cos, radians

from PySide6.QtCore import QPointF, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QDesktopServices
from PySide6.QtWidgets import QWidget

from .overview_map import MAPS, OverviewView, basemap_image, draw_place_names
from .widgets import MUTED, NAVY, label

ESTATE_CENTER = (50.08565, 19.99696)
TEAL = '#147D69'
LOCAL_LAYERS = ('green', 'parking', 'building', 'path', 'street', 'major')
LOCAL_STREETS = {'Stanisława Skarżyńskiego': 'ul. Skarżyńskiego',
                 'Izydora Stella-Sawickiego': 'ul. Stella-Sawickiego',
                 'Aleja Generała Tadeusza Bora-Komorowskiego': 'al. Bora-Komorowskiego',
                 'Romana Florera': 'ul. Florera'}

@lru_cache(maxsize=1)
def estate_features():
    return json.loads((MAPS / 'czyzyny-osm.json').read_text(encoding='utf-8'))


class CampusMap(QWidget):
    selected = Signal(str)

    def __init__(self, data, *, overview=False):
        super().__init__()
        self.dorms = data['dorms']
        self.campus = data['campus']
        self.overview = overview
        cutoff = data.get('min_distance')
        self.radius = float(cutoff) if cutoff is not None else None
        self.active = ''
        self.markers = {}
        self.setMinimumHeight(348 if overview else 322)
        self.setAccessibleName('Mapa Krakowa i promień przydziału' if overview else 'Mapa domów studenckich w Czyżynach')
        if not overview:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def attribution(self):
        item = label('', 10, MUTED, wrap=True)
        item.setTextFormat(Qt.TextFormat.RichText)
        sources = '<a style="color:#53667E;" href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a> · ODbL'
        if self.overview:
            sources += ' · <a style="color:#53667E;" href="https://www.naturalearthdata.com/">Natural Earth</a>'
        item.setText(sources)
        item.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        return item

    def highlight(self, code):
        self.active = code
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(area, 12, 12)
        painter.setClipPath(clip)
        if self.overview:
            view = OverviewView(area, self.campus, self.radius)
            self.draw_overview(painter, area, view)
            self.draw_scale(painter, area, view.scale, view.scale_bar())
            return

        center = ESTATE_CENTER
        scale = min((area.height() - 18) / .28, max(area.width() / .57, area.height() / .43))
        lon_factor = 111.195 * cos(radians(center[0]))

        def project(latitude, longitude):
            return QPointF(area.center().x() + (longitude - center[1]) * lon_factor * scale,
                           area.center().y() - (latitude - center[0]) * 111.195 * scale)

        self.draw_estate(painter, area, project)
        self.draw_scale(painter, area, scale, .05)

    def draw_estate(self, painter, area, project):
        painter.fillRect(area, QColor('#F1EFE7'))
        features = estate_features()
        selected = next((project(dorm['latitude'], dorm['longitude']) for dorm in self.dorms if dorm['code'] == self.active), None)
        street_names = {}
        for layer in LOCAL_LAYERS:
            for kind, name, coords in features:
                if kind != layer:
                    continue
                line = QPolygonF([project(lat, lon) for lat, lon in coords])
                if not line.boundingRect().adjusted(-5, -5, 5, 5).intersects(area):
                    continue
                if kind in ('green', 'parking', 'building'):
                    chosen = kind == 'building' and selected is not None and line.containsPoint(selected, Qt.FillRule.OddEvenFill)
                    colors = {'green': ('#D5E5CA', '#BCDBAD'), 'parking': ('#E6E6E3', '#D3D5CF'), 'building': ('#D6C8BE', '#AB9C91')}
                    fill, edge = ('#8BCEB8', TEAL) if chosen else colors[kind]
                    painter.setBrush(QColor(fill))
                    painter.setPen(QPen(QColor(edge), 1.8 if chosen else 0.65))
                    painter.drawPolygon(line)
                    continue
                if kind == 'path':
                    painter.setPen(QPen(QColor('#B9C3B6'), 1.4, Qt.PenStyle.DashLine))
                    painter.drawPolyline(line)
                    continue
                stroke = 8 if kind == 'major' else 5
                painter.setPen(QPen(QColor('#D5CABA'), stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.drawPolyline(line)
                painter.setPen(QPen(QColor('#FFFEF9'), stroke - 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.drawPolyline(line)
                if name in LOCAL_STREETS:
                    for i in range(len(line) - 1):
                        segment = line[i + 1] - line[i]
                        middle = line[i] + segment / 2
                        if area.adjusted(52, 18, -52, -27).contains(middle):
                            length = segment.manhattanLength()
                            if length > street_names.get(name, (0, None))[0]:
                                street_names[name] = length, middle
        painter.setFont(QFont('Segoe UI', 8))
        painter.setPen(QColor('#575D56'))
        for name, (_, point) in street_names.items():
            name_box = QRectF(point.x() - 64, point.y() - 10, 128, 16)
            painter.fillRect(name_box, QColor(255, 254, 249, 172))
            painter.drawText(name_box, Qt.AlignmentFlag.AlignCenter, LOCAL_STREETS[name])
        self.markers = {}
        for dorm in self.dorms:
            code = dorm['code']
            point = project(dorm['latitude'], dorm['longitude'])
            self.markers[code] = self.marker(painter, area, point, f"{code} · {dorm['name']}", code == self.active)

    def draw_overview(self, painter, area, view):
        base = basemap_image(self.width(), self.height(), self.devicePixelRatioF(), tuple(self.campus), self.radius)
        painter.drawPixmap(0, 0, base)
        if self.radius:
            radius_px = self.radius * view.scale
            painter.setPen(QPen(QColor(TEAL), 2.4))
            painter.setBrush(QColor(20, 125, 105, 33))
            painter.drawEllipse(view.origin, radius_px, radius_px)
        draw_place_names(painter, view)
        if view.scale > 24 and self.dorms:
            dorm = self.dorms[0]
            estate = view.project(dorm['latitude'], dorm['longitude'])
            if area.adjusted(16, 25, -18, -18).contains(estate):
                self.marker(painter, area, estate, 'Osiedle w Czyżynach')
        self.marker(painter, area, view.origin, 'Kampus Warszawska' if view.scale > 9 else 'Kraków · kampus PK', True)
        if self.radius is not None:
            caption = f'Promień {self.radius:.2f} km'.replace('.', ',')
            painter.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
            badge = QRectF(area.left() + 9, area.top() + 9, painter.fontMetrics().horizontalAdvance(caption) + 20, 25)
            painter.setPen(QPen(QColor('#D1E0DB'), 1))
            painter.setBrush(QColor('#FBFEFC'))
            painter.drawRoundedRect(badge, 6, 6)
            painter.setPen(QColor(TEAL))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, caption)

    @staticmethod
    def marker(painter, area, point, name, active=False):
        accent = QColor(TEAL if active else NAVY)
        painter.setPen(QPen(QColor('white'), 2.1))
        painter.setBrush(accent)
        radius = 8.5 if active else 6.5
        painter.drawEllipse(point, radius, radius)
        painter.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
        width = painter.fontMetrics().horizontalAdvance(name) + 14
        x = min(point.x() + 12, area.right() - width - 4)
        bounds = QRectF(x, point.y() - 10, width, 20)
        painter.setPen(QPen(accent, 1.2) if active else QPen(QColor('#CDD6D9'), 0.8))
        painter.setBrush(QColor('#EEF9F4' if active else '#FFFFFF'))
        painter.drawRoundedRect(bounds, 4, 4)
        painter.setPen(accent)
        painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, name)
        return bounds.united(QRectF(point.x() - 11, point.y() - 11, 22, 22))

    @staticmethod
    def draw_scale(painter, area, scale, length):
        painter.setFont(QFont('Segoe UI', 8))
        width = length * scale
        left, bottom = area.left() + 7, area.bottom() - 7
        painter.setPen(QPen(QColor('#D6DDD8'), 1))
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawRoundedRect(QRectF(left, bottom - 29, max(width, 32) + 12, 29), 5, 5)
        painter.setPen(QPen(QColor(NAVY), 1.9))
        painter.drawLine(QPointF(left + 6, bottom - 19), QPointF(left + 6 + width, bottom - 19))
        painter.drawText(QPointF(left + 6, bottom - 6), f'{length * 1000:g} m' if length < 1 else f'{length:g} km')
        badge = QRectF(area.right() - 30, area.top() + 6, 23, 24)
        painter.setBrush(QColor('white'))
        painter.setPen(QPen(QColor('#D6DDD8'), 1))
        painter.drawRoundedRect(badge, 5, 5)
        painter.setPen(QColor(NAVY))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, 'N ↑')

    def mousePressEvent(self, event):
        if self.overview or event.button() != Qt.MouseButton.LeftButton:
            return
        for code, hit in self.markers.items():
            if hit.contains(event.position()):
                self.selected.emit(code)
                break
