"""Native Qt visuals: faculty colours, readable results and an accessible timeline."""
from datetime import datetime
from decimal import Decimal
from math import cos, sin, pi
from .widgets import *

FACULTY_COLORS = ['#65A52D', '#009548', '#FF7900', '#E76722', '#0075AC', '#00B5E8', '#00A992', '#003571', '#79479B', '#CD007B', '#EF008D']
STATUS_COLORS = {'draft': '#64758B', 'submitted': '#2563A7', 'correction': '#A56A16',
                 'verified': '#087F8C', 'qualified': '#714696', 'confirmed': '#147D69',
                 'rejected': '#B23C47', 'waitlist': '#A56A16', 'expired': '#A56A16',
                 'withdrawn': '#64758B', 'canceled': '#B23C47'}


def tint(color, amount=.91):
    c = QColor(color)
    return QColor(*[round(v + (255 - v) * amount) for v in [c.red(), c.green(), c.blue()]]).name()


def short_date(value):
    if not value:
        return '—'
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone().strftime('%d.%m, %H:%M')


def status_chip(status, title):
    color = STATUS_COLORS.get(status, NAVY)
    return chip(title, color, tint(color))


def wr_formula():
    formula = QLabel()
    formula.setWordWrap(True)
    formula.setTextFormat(Qt.TextFormat.RichText)
    formula.setAccessibleName('WR to mniejsza z wartości: 1000 oraz 2 M plus 6 P jeden plus 2 P dwa plus D')
    formula.setText(
        '<span style="font-family:Cambria Math, Cambria, serif; font-size:23px; color:#003571;">'
        '<i>WR</i> = min (1&#8239;000; 2 · <i>M</i> + 6 · <i>P</i><sub>1</sub> + 2 · <i>P</i><sub>2</sub> + <i>D</i>)'
        '</span>'
    )
    return formula


class FacultyRibbon(QWidget):
    def __init__(self, height=10, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setAccessibleName('Barwy wydziałów Politechniki Krakowskiej')

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        step, height = self.width() / len(FACULTY_COLORS), self.height()
        for i, color in enumerate(FACULTY_COLORS):
            x = i * step
            p.setBrush(QColor(color))
            p.drawPolygon(QPolygonF([QPointF(x - height, 0), QPointF(x + step + height, 0),
                                    QPointF(x + step, height), QPointF(x - height * 2, height)]))
            p.setBrush(QColor(255, 255, 255, 22))
            p.drawPolygon(QPolygonF([QPointF(x, 0), QPointF(x + step * .4, 0), QPointF(x - height, height)]))
        p.end()


class FacultyHeader(QFrame):
    def __init__(self, title, subtitle, color=NAVY):
        super().__init__()
        self.setObjectName('facultyHeader')
        self.setStyleSheet(f'QFrame#facultyHeader {{background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #062B55,stop:1 {color}); border-radius:14px;}}')
        l = box(self, margins=22, spacing=8)
        l.addWidget(label(title, 25, '#FFFFFF', True, True))
        l.addWidget(label(subtitle, 13, '#FFFFFF', wrap=True))
        self.setMinimumHeight(102)


class HeroCarousel(QFrame):
    SLIDES = [
        ('TWOJA PRZYSZŁOŚĆ • TWOJE MOŻLIWOŚCI', 'Znajdź swoje miejsce\nwśród inżynierów.', '8 wydziałów. Wiele pasji. Wybierz kierunek, który pasuje do Ciebie.', '#77A43F', 'campus'),
        ('POMYSŁY, KTÓRE STAJĄ SIĘ RZECZYWISTOŚCIĄ', 'Od pierwszego pomysłu\ndo własnego projektu.', 'Architektura, informatyka, technologia i nauka. Poznaj kolory naszych wydziałów.', '#009EE3', 'network'),
        ('REKRUTACJA KROK PO KROKU', 'Wszystko, czego potrzebujesz,\nw jednym miejscu.', 'Dokumenty, wyniki i terminy. Twój następny krok jest zawsze pod ręką.', '#AF0A7F', 'orbit'),
    ]

    def __init__(self):
        super().__init__()
        self.index, self.paused = 0, False
        self.setMinimumHeight(270)
        self.setObjectName('carousel')
        outer = box(self, margins=26, spacing=12)
        self.panel = QWidget()
        content = box(self.panel, spacing=10)
        self.eyebrow = label('', 10, '#DAEAF8', True)
        self.heading = label('', 29, 'white', True, True)
        self.description = label('', 13, '#E4EFF9', wrap=True)
        for w in [self.eyebrow, self.heading, self.description]:
            content.addWidget(w)
        outer.addWidget(self.panel)
        outer.addStretch()
        controls = box(horizontal=True, spacing=8)
        self.prev = button('‹', lambda: self.set_slide(self.index - 1), secondary=True)
        self.prev.setAccessibleName('Poprzedni baner')
        self.next = button('›', lambda: self.set_slide(self.index + 1), secondary=True)
        self.next.setAccessibleName('Następny baner')
        self.counter = label('', 12, '#FFFFFF', True)
        self.pause = button('Wstrzymaj', self.toggle, secondary=True)
        for w in [self.prev, self.next]:
            w.setFixedWidth(42)
            w.setStyleSheet('padding:3px; background:#FFFFFF; color:#003571; border:none;')
        self.pause.setStyleSheet('padding:5px 12px; background:#FFFFFF; color:#003571; border:none;')
        controls.addWidget(self.prev)
        controls.addWidget(self.counter)
        controls.addWidget(self.next)
        controls.addStretch()
        controls.addWidget(self.pause)
        outer.addLayout(controls)
        self.effect = QGraphicsOpacityEffect(self.panel)
        self.panel.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b'opacity', self)
        self.animation.setDuration(260)
        self.timer = QTimer(self)
        self.timer.setInterval(6500)
        self.timer.timeout.connect(lambda: self.set_slide(self.index + 1) if not self.paused and not self.underMouse() else None)
        self.timer.start()
        self.set_slide(0)

    def toggle(self):
        self.paused = not self.paused
        self.pause.setText('Wznów' if self.paused else 'Wstrzymaj')

    def set_slide(self, index):
        self.index = index % len(self.SLIDES)
        eyebrow, title, description, self.color, self.art = self.SLIDES[self.index]
        self.eyebrow.setText(eyebrow)
        self.heading.setText(title)
        self.description.setText(description)
        self.counter.setText(f'{self.index + 1} / {len(self.SLIDES)}')
        self.setAccessibleName(title.replace('\n', ' ') + '. ' + description)
        self.animation.stop()
        self.animation.setStartValue(.45)
        self.animation.setEndValue(1.0)
        self.animation.start()
        self.update()

    def resizeEvent(self, event):
        self.panel.setMaximumWidth(max(470, int(self.width() * .68)))
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor('#062B55'))
        gradient.setColorAt(.55, QColor('#003571'))
        gradient.setColorAt(1, QColor(self.color))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gradient)
        p.drawRoundedRect(self.rect(), 18, 18)
        x, y, radius = self.width() * .83, self.height() * .46, 93
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawEllipse(QPointF(x, y), radius + 25, radius + 25)
        p.setPen(QPen(QColor(255, 255, 255, 150), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.art == 'campus':
            p.drawPolyline(QPolygonF([QPointF(x-90,y+45),QPointF(x-90,y-20),QPointF(x,y-60),QPointF(x+90,y-20),QPointF(x+90,y+45)]))
            p.drawLine(QPointF(x-105,y+48),QPointF(x+105,y+48))
            for dx in [-65,-25,15,55]:
                p.drawRoundedRect(QRectF(x+dx,y-5,14,49),3,3)
            p.drawEllipse(QPointF(x,y-27),12,12)
        elif self.art == 'network':
            points = [QPointF(x+cos(i*pi/3)*radius,y+sin(i*pi/3)*radius*.65) for i in range(6)]
            for point in points:
                p.drawLine(QPointF(x,y),point)
                p.drawEllipse(point,9,9)
            p.drawEllipse(QPointF(x,y),23,23)
            p.drawPolygon(QPolygonF(points))
        else:
            for i in range(3):
                p.save()
                p.translate(x,y)
                p.rotate(i*60)
                p.drawEllipse(QRectF(-90,-36,180,72))
                p.restore()
            p.setBrush(QColor('#E4C372'))
            p.drawEllipse(QPointF(x,y),11,11)
        p.end()


class ScoreCard(QFrame):
    def __init__(self, explanation, degree='I', heading='Skąd mój wynik?', published=True):
        super().__init__()
        self.setObjectName('card')
        l = box(self, margins=20, spacing=14)
        top = box(horizontal=True)
        top.addWidget(label(heading, 20, NAVY, True))
        top.addStretch()
        top.addWidget(chip('Wynik opublikowany' if published else 'Podgląd roboczy', '#147D69' if published else '#A56A16', '#EDF7F1' if published else '#FFF4DF'))
        l.addLayout(top)
        if degree == 'I':
            l.addWidget(wr_formula())
            terms = box(horizontal=True, spacing=10)
            for key, weight, color, name in [('M',2,'#009EE3','Matematyka'),('P1',6,'#77A43F','Pierwszy przedmiot'),('P2',2,'#714696','Drugi przedmiot'),('D',1,'#D3682B','Osiągnięcie')]:
                f = QFrame()
                f.setObjectName('scoreTerm')
                f.setStyleSheet(f'QFrame#scoreTerm {{ background:{tint(color)}; border-radius:10px; border-top:4px solid {color}; }}')
                b = box(f, margins=12, spacing=6)
                value = Decimal(str(explanation.get(key, 0)))
                b.addWidget(label(name, 10, MUTED, wrap=True))
                b.addWidget(label(f'{weight} × {value:g}' if key != 'D' else f'+ {value:g}', 19, NAVY, True))
                b.addWidget(label(f'{weight * value:g} pkt', 12, MUTED))
                terms.addWidget(f, 1)
            l.addLayout(terms)
            total = box(horizontal=True)
            total.addWidget(label('WSKAŹNIK REKRUTACYJNY', 10, MUTED, True))
            total.addStretch()
            total.addWidget(label(f"{Decimal(str(explanation.get('score',0))):g} / 1000", 30, NAVY, True))
            l.addLayout(total)
            if Decimal(str(explanation.get('uncapped', 0))) > 1000:
                l.addWidget(chip('Zastosowano limit 1000 punktów', '#A56A16', '#FFF4DF'))
            if explanation.get('P2_before_portfolio') != explanation.get('P2'):
                l.addWidget(label(f"Wyróżnione portfolio: P2 wzrosło z {explanation.get('P2_before_portfolio', '—')} do 100.", 12, '#714696', wrap=True))
        elif degree == 'II':
            l.addWidget(label(str(explanation.get('average', '—')), 38, '#77A43F', True))
            l.addWidget(label('Średnia ze studiów I stopnia • jedyne kryterium rankingu', 13, MUTED, wrap=True))
        else:
            l.addWidget(label('Liczy się kolejność zgłoszeń', 23, '#714696', True))
            l.addWidget(label('Kompletne zgłoszenie: ' + short_date(explanation.get('submitted_at')), 14, MUTED))


class RoundTimeline(QWidget):
    def __init__(self, round_, now, color):
        super().__init__()
        self.round, self.now, self.color = round_, datetime.fromisoformat(now.replace('Z','+00:00')), color
        self.setMinimumHeight(190)
        self.setAccessibleName(f"Tura {round_['number']}: zapisy {short_date(round_['start'])} – {short_date(round_['application_end'])}; następnie wyniki i potwierdzenie do {short_date(round_['end'])}.")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right, y = 24, self.width()-24, 74
        start, cutoff, end = [datetime.fromisoformat(self.round[k].replace('Z','+00:00')) for k in ['start','application_end','end']]
        middle = left + (right-left)*(cutoff-start).total_seconds()/(end-start).total_seconds()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(tint(self.color,.78)))
        p.drawRoundedRect(QRectF(left,y-13,middle-left,26),8,8)
        p.setBrush(QColor('#EAE2F4'))
        p.drawRoundedRect(QRectF(middle,y-13,right-middle,26),8,8)
        p.setPen(QColor(NAVY))
        p.setFont(QFont('Segoe UI',12,QFont.Weight.Bold))
        p.drawText(QRectF(left,6,right-left,24),Qt.AlignmentFlag.AlignLeft,f"Tura {self.round['number']}")
        phase = 'Zakończona' if self.now >= end else 'Zapisy otwarte' if start <= self.now < cutoff else 'Wyniki i potwierdzenia' if cutoff <= self.now < end else 'Przed nami'
        p.setFont(QFont('Segoe UI',10))
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(left,6,right-left,24),Qt.AlignmentFlag.AlignRight,phase)
        p.setPen(QColor(NAVY))
        p.drawText(QRectF(left+14,y-13,middle-left-28,26),Qt.AlignmentFlag.AlignVCenter,'Przyjmowanie zgłoszeń')
        p.drawText(QRectF(middle+12,y-13,right-middle-20,26),Qt.AlignmentFlag.AlignVCenter,'Potwierdzenia')
        for x, title, date_, done in [(left,'Start zapisów',start,self.now>=start),(middle,'Koniec zapisów',cutoff,self.now>=cutoff),(right,'Koniec tury',end,self.now>=end)]:
            p.setPen(QPen(QColor(self.color if done else '#B7C7DA'),2))
            p.setBrush(QColor(self.color if done else 'white'))
            p.drawEllipse(QPointF(x,y),6,6)
            p.setPen(QColor(NAVY))
            rect = QRectF(max(0,min(x-100,self.width()-200)),105,200,26)
            align = Qt.AlignmentFlag.AlignLeft if x==left else Qt.AlignmentFlag.AlignRight if x==right else Qt.AlignmentFlag.AlignHCenter
            p.drawText(rect,align,title)
            p.setPen(QColor(MUTED))
            p.drawText(rect.translated(0,26),align,date_.astimezone().strftime('%d.%m, %H:%M'))
        p.setPen(QColor('#714696'))
        p.drawText(QRectF(left, 158, right-left, 24), Qt.AlignmentFlag.AlignRight,
                   '◆  Ogłoszenie wyników po weryfikacji, przed końcem tury')
        if start <= self.now <= end:
            x = left+(right-left)*(self.now-start).total_seconds()/(end-start).total_seconds()
            p.setPen(QPen(QColor('#D29B32'),2,Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x,y-32),QPointF(x,y+28))
        p.end()
