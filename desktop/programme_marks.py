from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .visuals import tint

FACULTY_MARKS = {
    'WA': 'building', 'WIiM': 'code', 'WIEiK': 'chip', 'WILiT': 'bridge',
    'WIMiF': 'lattice', 'WIŚiE': 'energy', 'WIiTCh': 'flask', 'WM': 'mechanism',
}
PROGRAMME_MARKS = {
    'Architektura krajobrazu': 'leaf', 'Matematyka stosowana': 'geometry',
    'Fizyka techniczna': 'geometry', 'Informatyka stosowana': 'code',
}


class ProgrammeMark(QWidget):
    def __init__(self, offer, *, compact=False):
        super().__init__()
        self.mark = PROGRAMME_MARKS.get(offer['name'], FACULTY_MARKS.get(offer['faculty'], 'geometry'))
        self.accent = QColor(offer['color'])
        self.background = QColor(tint(offer['color']))
        width, height = (54, 40) if compact else (94, 70)
        self.setFixedSize(width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.background)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0, 0, -1, -1), 13, 13)
        painter.scale(self.width() / 94, self.height() / 70)
        painter.translate(24, 12)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self.accent.darker(123), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        def line(*points):
            painter.drawPolyline(QPolygonF([QPointF(x, y) for x, y in points]))

        if self.mark == 'code':
            painter.drawRoundedRect(3, 6, 39, 31, 3, 3)
            line((17, 15), (11, 21), (17, 27))
            line((28, 15), (34, 21), (28, 27))
            line((25, 14), (20, 28))
        elif self.mark == 'chip':
            painter.drawRoundedRect(9, 9, 28, 28, 3, 3)
            painter.drawRect(17, 17, 12, 12)
            for x in (15, 23, 31):
                line((x, 3), (x, 9))
                line((x, 37), (x, 43))
                line((3, x), (9, x))
                line((37, x), (43, x))
        elif self.mark == 'lattice':
            line((10, 12), (25, 4), (37, 15), (32, 32), (17, 41), (6, 29), (10, 12), (22, 23), (37, 15))
            line((22, 23), (32, 32))
            line((6, 29), (22, 23), (25, 4))
            for x, y in [(10, 12), (25, 4), (37, 15), (22, 23), (6, 29), (32, 32), (17, 41)]:
                painter.drawEllipse(QPointF(x, y), 2.2, 2.2)
        elif self.mark == 'building':
            line((3, 17), (23, 5), (43, 17), (3, 17))
            for x in (10, 18, 28, 36):
                line((x, 18), (x, 38))
            line((4, 39), (42, 39))
        elif self.mark == 'bridge':
            line((3, 34), (43, 34))
            line((12, 40), (12, 20), (23, 5), (34, 20), (34, 40))
            line((23, 5), (7, 33))
            line((23, 5), (39, 33))
            line((23, 13), (23, 34))
        elif self.mark == 'energy':
            line((27, 4), (9, 25), (22, 25), (19, 43), (37, 21), (24, 21), (27, 4))
        elif self.mark == 'flask':
            line((17, 5), (29, 5))
            line((19, 5), (19, 18), (7, 37), (9, 41), (37, 41), (39, 37), (27, 18), (27, 5))
            line((13, 29), (33, 29))
            painter.drawEllipse(19, 32, 4, 4)
        elif self.mark == 'mechanism':
            painter.drawEllipse(11, 11, 24, 24)
            painter.drawEllipse(19, 19, 8, 8)
            for a, b in [((23, 5),(23,11)), ((23,35),(23,41)), ((5,23),(11,23)), ((35,23),(41,23)),
                         ((10,10),(14,14)), ((36,36),(32,32)), ((36,10),(32,14)), ((10,36),(14,32))]:
                line(a, b)
        elif self.mark == 'leaf':
            painter.drawEllipse(13, 5, 21, 31)
            line((13, 41), (25, 17), (29, 13))
            line((20, 29), (17, 19))
            line((23, 24), (30, 23))
        else:
            line((4, 36), (23, 6), (42, 36), (4, 36))
            line((23, 6), (23, 36))
            painter.drawEllipse(QPointF(23, 26), 6, 6)
