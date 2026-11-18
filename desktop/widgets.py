from PySide6.QtCore import Qt, QSize, QRectF, QPointF, QTimer, QPropertyAnimation
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPixmap, QIcon, QPainterPath, QPolygonF, QLinearGradient, QPalette
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QHeaderView, QAbstractItemView, QTableWidgetItem,
    QScrollArea, QSizePolicy, QListView, QGraphicsOpacityEffect, QStyle, QStyledItemDelegate)

NAVY = '#003571'
MUTED = '#64758B'
PAGE_BACKGROUND = '#F3F6FB'


def line_icon(name, color='#C2D1E4'):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if name in ['dashboard', 'catalog']:
        for x, y in [(4,4),(14,4),(4,14),(14,14)]:
            p.drawRoundedRect(x,y,6,6,1,1)
    elif name in ['applications', 'review', 'thresholds']:
        p.drawRoundedRect(5,3,14,18,2,2)
        for y in [8,12,16]:
            p.drawLine(8,y,16,y)
    elif name == 'timeline':
        p.drawEllipse(3,3,18,18)
        p.drawLine(12,6,12,12)
        p.drawLine(12,12,16,14)
    elif name == 'ranking':
        for x, y in [(4,14), (10,9), (16,4)]:
            p.drawRoundedRect(x,y,4,21-y,1,1)
    elif name == 'discover':
        p.drawEllipse(3,3,18,18)
        p.drawPolygon(QPolygonF([QPointF(16,7),QPointF(13,14),QPointF(7,17),QPointF(10,10)]))
    elif name == 'campus':
        p.drawPolyline(QPolygonF([QPointF(3,8),QPointF(12,3),QPointF(21,8),QPointF(3,8)]))
        for x in [6,12,18]:
            p.drawLine(x,11,x,18)
        p.drawLine(3,21,21,21)
    elif name == 'krakow':
        pin = QPainterPath(QPointF(12, 21))
        pin.cubicTo(10, 18, 5, 13, 5, 9)
        pin.cubicTo(5, 0, 19, 0, 19, 9)
        pin.cubicTo(19, 13, 14, 18, 12, 21)
        p.drawPath(pin)
        p.drawEllipse(QPointF(12, 9), 2.4, 2.4)
    elif name == 'housing':
        p.drawRoundedRect(5, 3, 14, 18, 2, 2)
        for y in (7, 11, 15):
            for x in (9, 15):
                p.drawPoint(x, y)
        p.drawLine(12, 18, 12, 21)
    elif name == 'external':
        p.drawLine(8,16,19,5)
        p.drawPolyline(QPolygonF([QPointF(12,5),QPointF(19,5),QPointF(19,12)]))
    elif name == 'lecturers':
        p.drawEllipse(8,8,8,8)
        p.drawPolygon(QPolygonF([QPointF(3,5),QPointF(12,1),QPointF(21,5),QPointF(12,9)]))
        p.drawLine(21,5,21,11)
        p.drawArc(4,16,16,13,0,180*16)
    elif name == 'profile':
        p.drawEllipse(8,3,8,8)
        p.drawArc(4,13,16,14,0,180*16)
    elif name == 'notifications':
        p.drawArc(6,4,12,15,0,180*16)
        p.drawLine(6,11,5,18)
        p.drawLine(18,11,19,18)
        p.drawLine(5,18,19,18)
        p.drawLine(10,21,14,21)
    elif name == 'admin':
        p.drawRoundedRect(5,10,14,11,2,2)
        p.drawArc(8,2,8,14,0,180*16)
        p.drawLine(12,14,12,17)
    elif name == 'refresh':
        p.drawArc(4,4,16,16,35*16,285*16)
        p.drawLine(20,5,20,10)
        p.drawLine(20,10,15,9)
    p.end()
    return QIcon(pixmap)

STYLE = '''
QWidget { font-family: "Segoe UI"; font-size: 13px; color: #1D2D46; }
QMainWindow, QWidget#root { background: #F3F6FB; }
QFrame#sidebar { background: #062B55; border: none; }
QFrame#card { background: white; border: 1px solid #E1E7F0; border-radius: 14px; }
QFrame#hero { background: #003571; border-radius: 18px; }
QFrame#topbar { background: white; border-bottom: 1px solid #E4EAF2; }
QLabel { background: transparent; border: none; }
QLabel#muted { color: #64758B; }
QPushButton { background: #003571; color: white; border: 1px solid #003571; border-radius: 8px; padding: 10px 18px; font-weight: 600; min-height: 20px; }
QPushButton:hover { background: #124C8C; border-color: #124C8C; }
QPushButton:pressed { background: #002853; }
QPushButton:disabled { background: #E1E7F0; color: #78869B; border-color: #E1E7F0; }
QPushButton:focus { border: 2px solid #E3A832; }
QPushButton[secondary="true"] { background: white; color: #003571; border: 1px solid #CFD9E6; }
QPushButton[secondary="true"]:hover { background: #EFF5FD; border-color: #9FB9D6; }
QPushButton[danger="true"] { background: #FFF3F2; color: #A73535; border-color: #EFCDCA; }
QPushButton[nav="true"] { text-align: left; background: transparent; border: none; color: #C2D1E4; padding: 9px 14px; border-radius: 9px; font-weight: 500; }
QPushButton[nav="true"]:hover { background: #133E6D; color: white; }
QPushButton[active="true"] { background: #234D79; color: white; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit { background: white; border: 1px solid #CCD7E5; border-radius: 7px; padding: 9px 11px; selection-background-color: #003571; selection-color: white; min-height: 20px; }
QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border: 2px solid #3D7BBA; }
QLineEdit:disabled { background: #EAF0F7; color: #65768B; }
QComboBox { combobox-popup: 0; padding-right: 25px; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: none; }
QComboBox QAbstractItemView { background: white; color: #1D2D46; selection-background-color: #003571; selection-color: white; border: 1px solid #CBD7E8; outline: 0; padding: 4px; }
QComboBox QAbstractItemView::item { min-height: 30px; padding: 4px 10px; }
QComboBox QAbstractItemView::item:selected, QComboBox QAbstractItemView::item:hover { background: #003571; color: white; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #F3F6FB; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #C1CDDC; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTableWidget { background: white; border: 1px solid #E0E7F0; border-radius: 10px; gridline-color: #EDF1F6; selection-background-color: #E8F1FD; selection-color: #12385F; alternate-background-color: #F8FAFD; }
QTableWidget::item { padding: 9px; border: none; }
QHeaderView::section { background: #F3F6FB; color: #65768B; padding: 12px 9px; border: none; border-bottom: 1px solid #DCE5F0; font-size: 11px; font-weight: 600; }
QDialog { background: #F5F7FB; }
QCheckBox { spacing: 8px; padding: 5px 0; }
QCheckBox::indicator { width: 18px; height: 18px; background: white; border: 1px solid #A5B8CE; border-radius: 4px; }
QCheckBox::indicator:checked { background: #147D69; border: 3px solid #BCE9D8; }
QToolTip { background: #12385F; color: white; border: none; padding: 8px; }
'''


def label(text, size=13, color=None, bold=False, wrap=False):
    item = QLabel(str(text))
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(wrap)
    font = QFont('Segoe UI', size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    item.setFont(font)
    item.setStyleSheet(f'font-size: {size}px; color: {color or "#1D2D46"}; font-weight: {600 if bold else 400};')
    return item


def button(text, callback=None, secondary=False, danger=False):
    item = QPushButton(text)
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    item.setProperty('secondary', secondary)
    item.setProperty('danger', danger)
    item.setAutoDefault(False)
    if callback:
        item.clicked.connect(callback)
    return item


class NavigationButton(QPushButton):
    def __init__(self, key, title, callback, unread=0):
        super().__init__(title)
        self.unread = unread
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoDefault(False)
        self.setProperty('nav', True)
        self.setIcon(line_icon(key))
        self.setIconSize(QSize(20, 20))
        self.clicked.connect(callback)
        if unread:
            accessible = f'{title} · nieodczytane: {unread}'
            self.setAccessibleName(accessible)
            self.setToolTip(accessible)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.unread:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#FF575F'))
            painter.drawEllipse(QPointF(self.width() - 17, self.height() / 2), 4.5, 4.5)


def box(parent=None, spacing=12, margins=0, horizontal=False):
    layout = QHBoxLayout(parent) if horizontal else QVBoxLayout(parent)
    layout.setContentsMargins(margins, margins, margins, margins)
    layout.setSpacing(spacing)
    return layout


def card(margins=22):
    frame = QFrame()
    frame.setObjectName('card')
    return frame, box(frame, margins=margins)


def chip(text, color='#003571', background='#EAF1FA'):
    item = label(text, 11, color, True)
    item.setStyleSheet(f'color: {color}; background: {background}; border-radius: 5px; padding: 5px 8px; font-size: 11px; font-weight: 600;')
    item.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return item


def field(layout, title, value='', placeholder='', secret=False):
    layout.addWidget(label(title, 12, MUTED, True))
    item = QLineEdit(str(value))
    item.setPlaceholderText(placeholder)
    if secret:
        item.setEchoMode(QLineEdit.EchoMode.Password)
    item.setAccessibleName(title)
    layout.addWidget(item)
    return item


class SelectBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(MUTED), 1.5))
        x, y = self.width() - 15, self.height() / 2
        p.drawPolyline(QPolygonF([QPointF(x-4, y-2), QPointF(x, y+2), QPointF(x+4, y-2)]))


def combo(items, label_text=''):
    item = SelectBox()
    view = QListView()
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    view.setUniformItemSizes(True)
    item.setView(view)
    item.setMaxVisibleItems(8)
    palette = item.view().palette()
    for group in [QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive]:
        palette.setColor(group, QPalette.ColorRole.Highlight, QColor(NAVY))
        palette.setColor(group, QPalette.ColorRole.HighlightedText, QColor('white'))
        palette.setColor(group, QPalette.ColorRole.Text, QColor('#1D2D46'))
    item.view().setPalette(palette)
    item.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    item.setMinimumContentsLength(9)
    item.setMinimumWidth(100)
    item.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    item.setAccessibleName(label_text)
    for title, data in items:
        item.addItem(title, data)
    return item


class RowDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus


def table(headers, rows, stretch=0):
    view = QTableWidget(len(rows), len(headers))
    view.setHorizontalHeaderLabels(headers)
    view.verticalHeader().hide()
    view.verticalHeader().setDefaultSectionSize(48)
    view.setAlternatingRowColors(True)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setItemDelegate(RowDelegate(view))
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setShowGrid(False)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    view.horizontalHeader().setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            view.setItem(r, c, QTableWidgetItem(str(value)))
    return view


def scroll_page():
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    body = QWidget()
    body.setObjectName('pageBody')
    body.setStyleSheet('QWidget#pageBody { background: transparent; }')
    layout = box(body, spacing=22, margins=30)
    scroll.setWidget(body)
    return scroll, body, layout


class Journey(QWidget):
    def __init__(self, stages, current=0, dark=False):
        super().__init__()
        self.stages, self.current, self.dark = stages, current, dark
        self.setMinimumHeight(100)
        self.setAccessibleName('Etapy rekrutacji: ' + ', '.join(stages))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width() / len(self.stages)
        for i, title in enumerate(self.stages):
            x, y = int(width * (i + .5)), 29
            if i < len(self.stages) - 1:
                p.setPen(QPen(QColor('#45719C' if self.dark else '#D6E1EE'), 2))
                p.drawLine(x + 21, y, int(x + width - 21), y)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#D7AF62' if i == self.current else '#315C86' if self.dark else '#E8EFF7'))
            p.drawEllipse(x - 17, y - 17, 34, 34)
            p.setPen(QColor('#173D63' if i == self.current else '#FFFFFF' if self.dark else '#64758B'))
            p.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
            p.drawText(x - 17, y - 17, 34, 34, Qt.AlignmentFlag.AlignCenter, str(i + 1))
            p.setFont(QFont('Segoe UI', 9))
            p.setPen(QColor('#D6E3F2' if self.dark else '#64758B'))
            p.drawText(int(x - width / 2), 57, int(width), 36, Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap, title)
        p.end()
