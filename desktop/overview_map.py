"""Vector basemap and distance-preserving projection for housing statistics."""
from functools import lru_cache
import json
from math import atan2, ceil, cos, floor, hypot, log10, radians, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from portable import ROOT

MAPS = ROOT / 'assets' / 'maps'
EARTH_RADIUS_KM = 6371.0088
LAND = '#F1F1E9'
NEIGHBOURHOODS = (
    ('Krowodrza', 50.0808, 19.9185),
    ('Stare Miasto', 50.0606, 19.9331),
    ('Grzegórzki', 50.0628, 19.9693),
    ('Kazimierz', 50.0515, 19.9448),
    ('Czyżyny', 50.0779, 20.0050),
    ('Dębniki', 50.0480, 19.9241),
)
REGIONAL_CITIES = (
    ('Skawina', 49.9768, 19.8281), ('Wieliczka', 49.9871, 20.0649), ('Niepołomice', 50.0359, 20.2180),
    ('Bochnia', 49.9696, 20.4291), ('Myślenice', 49.8335, 19.9385), ('Olkusz', 50.2790, 19.5652),
    ('Chrzanów', 50.1398, 19.4046), ('Wadowice', 49.8835, 19.4936), ('Oświęcim', 50.0392, 19.2230),
    ('Katowice', 50.2599, 19.0216), ('Tarnów', 50.0121, 20.9858), ('Kielce', 50.8661, 20.6255),
    ('Nowy Sącz', 49.6239, 20.6971), ('Zakopane', 49.2992, 19.9507), ('Rzeszów', 50.0374, 22.0047),
    ('Warszawa', 52.2297, 21.0122), ('Wrocław', 51.1079, 17.0385), ('Łódź', 51.7592, 19.4560),
    ('Brno', 49.1951, 16.6068), ('Żylina', 49.2231, 18.7393),
)


class OverviewView:
    def __init__(self, area, campus, radius):
        self.area = area
        self.origin = area.center()
        self.scale = min(area.width(), area.height()) * .33 / max(radius if radius is not None else 3.3, .28)
        latitude, longitude = campus
        lat, self.lon = radians(latitude), radians(longitude)
        self.sin_lat, self.cos_lat = sin(lat), cos(lat)
        lat_span = area.height() / (self.scale * 111.195 * 2) * 1.25
        lon_span = area.width() / (self.scale * 111.195 * self.cos_lat * 2) * 1.25
        self.bounds = (latitude - lat_span, longitude - lon_span, latitude + lat_span, longitude + lon_span)

    def project(self, latitude, longitude):
        """Azimuthal equidistant projection centered on the PK campus."""
        lat, lon_delta = radians(latitude), radians(longitude) - self.lon
        sin_lat, cos_lat = sin(lat), cos(lat)
        x = cos_lat * sin(lon_delta)
        y = self.cos_lat * sin_lat - self.sin_lat * cos_lat * cos(lon_delta)
        radial = hypot(x, y)
        if radial < 1e-12:
            return self.origin
        z = self.sin_lat * sin_lat + self.cos_lat * cos_lat * cos(lon_delta)
        factor = self.scale * EARTH_RADIUS_KM * atan2(radial, z) / radial
        return self.origin + QPointF(x * factor, -y * factor)

    def visible(self, bounds):
        south, west, north, east = self.bounds
        return not (bounds[2] < south or bounds[0] > north or bounds[3] < west or bounds[1] > east)

    def scale_bar(self):
        target = 76 / self.scale
        unit = 10 ** floor(log10(target))
        return max(unit * step for step in (1, 2, 5) if unit * step <= target)


@lru_cache(maxsize=3)
def feature_layers(filename):
    rows = json.loads((MAPS / filename).read_text(encoding='utf-8'))
    layers = {}
    for kind, coordinates in rows:
        lat, lon = zip(*coordinates)
        bounds = (min(lat), min(lon), max(lat), max(lon))
        layers.setdefault(kind, []).append((bounds, coordinates))
    return layers


def paths_for(view, features, *, closed=False):
    path = QPainterPath()
    for bounds, coordinates in features:
        if view.visible(bounds):
            path.addPolygon(QPolygonF([view.project(*point) for point in coordinates]))
            if closed:
                path.closeSubpath()
    return path


def stroke(painter, path, color, width):
    painter.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)


def fill(painter, path, color, border=None):
    painter.setPen(QPen(QColor(border), .86) if border else Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawPath(path)


def draw_basemap(painter, view):
    painter.fillRect(view.area, QColor(LAND))
    if view.scale < 9:
        countries = feature_layers('granice-natural-earth.json')
        for code, shapes in countries.items():
            fill(painter, paths_for(view, shapes, closed=True), LAND if code == 'POL' else '#E6EBE2', '#BCCBC1')

    if view.scale < 28:
        region = feature_layers('region-natural-earth.json')
        stroke(painter, paths_for(view, region.get('road', [])), '#D2D5CC', 1.)
        stroke(painter, paths_for(view, region.get('river', [])), '#AFCEDB', 1.2)
    if view.scale < 7:
        return

    city = feature_layers('krakow-osm.json')
    fill(painter, paths_for(view, city.get('park', []), closed=True), '#DBEAD6')
    fill(painter, paths_for(view, city.get('water', []), closed=True), '#B7D7E6')
    stroke(painter, paths_for(view, city.get('river', [])), '#B7D7E6', max(2.2, min(10., view.scale * .09)))
    if view.scale >= 43:
        stroke(painter, paths_for(view, city.get('street', [])), '#FCFCF8', 1.35)
    avenues = paths_for(view, city.get('avenue', []))
    stroke(painter, avenues, '#DADFD5', 3.)
    stroke(painter, avenues, '#FFFDF6', 1.9)
    arterial = paths_for(view, city.get('arterial', []))
    stroke(painter, arterial, '#DFD8C5', 4.1)
    stroke(painter, arterial, '#FFF9EB', 2.8)


@lru_cache(maxsize=4)
def basemap_image(width, height, device_scale, campus, radius):
    frame = QPixmap(ceil(width * device_scale), ceil(height * device_scale))
    frame.setDevicePixelRatio(device_scale)
    frame.fill(QColor(LAND))
    painter = QPainter(frame)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_basemap(painter, OverviewView(QRectF(1, 1, width - 2, height - 2), campus, radius))
    painter.end()
    return frame


def draw_place_names(painter, view):
    canvas = view.area.adjusted(12, 45, -84, -35)
    painter.setFont(QFont('Segoe UI', 8, QFont.Weight.DemiBold))
    painter.setPen(QColor('#526761'))
    painter.setBrush(QColor('#526761'))
    places = NEIGHBOURHOODS if view.scale >= 25 else REGIONAL_CITIES
    occupied = []
    for name, lat, lon in places:
        point = view.project(lat, lon)
        if not canvas.contains(point) or (point - view.origin).manhattanLength() < 55:
            continue
        if any((point - other).manhattanLength() < 75 for other in occupied):
            continue
        occupied.append(point)
        if view.scale < 25:
            painter.drawEllipse(point, 2., 2.)
        painter.drawText(point + QPointF(5, 4), name)
