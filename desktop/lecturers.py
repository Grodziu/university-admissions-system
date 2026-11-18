"""Native, offline faculty explorer with animated portraits and research maps."""
import os
from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath, QPolygonF
from PySide6.QtWidgets import QWidget, QPushButton, QGridLayout, QSizePolicy, QButtonGroup
from admissions.academic_staff import catalog
from .programme_marks import ProgrammeMark
from .visuals import tint
from .widgets import NAVY, MUTED, box, card, label
from .discover import website


def avatar(p, area, variant, accent):
    """Editorial illustration of a fictional person, drawn as vector shapes."""
    p.save()
    path = QPainterPath()
    path.addEllipse(area)
    p.setClipPath(path)
    p.fillRect(area, QColor(tint(accent, .85)))
    p.translate(area.left(), area.top())
    p.scale(area.width()/100, area.height()/100)
    skin = ['#E7B797','#AF7963','#D9A783','#F0C8AC'][variant % 4]
    hair = ['#253E53','#533B3F','#735644','#36424F'][variant % 4]
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(accent).darker(118))
    p.drawRoundedRect(QRectF(16,71,68,55),22,22)
    p.setBrush(QColor('#FFFFFF'))
    p.drawPolygon(QPolygonF([QPointF(38,71),QPointF(50,89),QPointF(62,71)]))
    p.setBrush(QColor(skin))
    p.drawRoundedRect(QRectF(44,60,13,17),4,4)
    p.setBrush(QColor(hair))
    p.drawEllipse(QRectF(28,15,44,49))
    if variant % 3 == 0:
        p.drawRoundedRect(QRectF(27,30,46,45),15,15)
    p.setBrush(QColor(skin))
    p.drawEllipse(QRectF(31,25,38,43))
    p.setBrush(QColor(hair))
    p.drawChord(QRectF(28,14,43,35),0,180*16)
    p.setPen(QPen(QColor('#344153'),1.9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(41,44),QPointF(43,44))
    p.drawLine(QPointF(57,44),QPointF(59,44))
    p.drawArc(QRectF(44,49,13,11),190*16,150*16)
    if variant % 2:
        p.setPen(QPen(QColor('#36506B'),1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(35,39,12,10),3,3)
        p.drawRoundedRect(QRectF(53,39,12,10),3,3)
        p.drawLine(QPointF(47,43),QPointF(53,43))
    p.restore()


class Portrait(QWidget):
    def __init__(self, person, accent, animate):
        super().__init__()
        self.person, self.accent = person, accent
        self.setFixedSize(92, 92)
        self.inset = 1
        self.setAccessibleName('Portret: '+person['name'])
        if animate and os.environ.get('PK_REDUCE_MOTION') != '1':
            self.inset = 12
            self.animation = QVariantAnimation(self, duration=240, easingCurve=QEasingCurve.Type.OutCubic)
            self.animation.setStartValue(12.)
            self.animation.setEndValue(1.)
            self.animation.valueChanged.connect(self.set_inset)
            self.animation.start()

    def set_inset(self, value):
        self.inset = value
        self.update()

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = self.inset
        avatar(p, QRectF(self.rect()).adjusted(inset, inset, -inset, -inset),
               self.person['avatar'], self.accent)


class PersonButton(QPushButton):
    def __init__(self, person, accent, parent):
        super().__init__(person['name'],parent)
        self.person,self.accent,self.focus_amount=person,accent,0.
        self.setCheckable(True)
        self.setAccessibleName('Poznaj: '+person['name'])
        self.setObjectName('lecturer-'+person['id'])
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.animation=QVariantAnimation(self,duration=260,easingCurve=QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.set_amount)

    def set_amount(self,value):
        self.focus_amount=float(value); self.update()

    def select(self,chosen,animate=True):
        self.setChecked(chosen); self.animation.stop()
        if not animate or os.environ.get('PK_REDUCE_MOTION')=='1':
            self.set_amount(1. if chosen else 0.); return
        self.animation.setStartValue(self.focus_amount)
        self.animation.setEndValue(1. if chosen else 0.)
        self.animation.start()

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(self.rect()).adjusted(2,2,-2,-2)
        p.setBrush(QColor(tint(self.accent,.93) if self.isChecked() else '#FFFFFF'))
        p.setPen(QPen(QColor(self.accent if self.isChecked() else '#DAE4EF'),2 if self.isChecked() else 1))
        p.drawRoundedRect(rect,16,16)
        size=54+16*self.focus_amount
        avatar(p,QRectF((self.width()-size)/2,10+(70-size)/2,size,size),self.person['avatar'],self.accent)
        p.setPen(QColor(NAVY)); p.setFont(QFont('Segoe UI',10,QFont.Weight.DemiBold))
        p.drawText(QRectF(7,82,self.width()-14,45),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,self.person['name'])
        p.setPen(QColor(self.accent).darker(125)); p.setFont(QFont('Segoe UI',9))
        p.drawText(QRectF(8,127,self.width()-16,38),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,self.person['focus'])
        if self.hasFocus():
            p.setPen(QPen(QColor('#DDA52A'),2,Qt.PenStyle.DashLine)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(4,4,-4,-4),12,12)


class PeopleMap(QWidget):
    CARD_HEIGHT = 174
    FIRST_ROW = 74
    GAP = 10

    def __init__(self,faculty,people,selected,on_select):
        super().__init__()
        self.faculty = faculty
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.buttons=[]
        self.person_group = QButtonGroup(self)
        self.mark=ProgrammeMark({'name':'','faculty':faculty['code'],'color':faculty['color']}, compact=True)
        self.mark.setParent(self)
        for person in people:
            item=PersonButton(person,faculty['color'],self)
            self.person_group.addButton(item)
            item.clicked.connect(lambda checked=False,p=person:on_select(p['id']))
            item.select(person['id']==selected,False)
            self.buttons.append(item)
        self.setFixedHeight(self.FIRST_ROW + self.CARD_HEIGHT + self.GAP)
        self.setAccessibleName('Mapa prowadzących: '+faculty['name'])

    def resizeEvent(self,event):
        width = self.width()
        columns = min(len(self.buttons), 3 if width >= 402 else 2)
        gap = self.GAP
        card_width = min(172, (width - (columns + 1) * gap) // columns)
        self.mark.move((width - self.mark.width()) // 2, 10)
        for row, start in enumerate(range(0, len(self.buttons), columns)):
            items = self.buttons[start:start + columns]
            row_width = len(items) * card_width + (len(items) - 1) * gap
            left = (width - row_width) // 2
            top = self.FIRST_ROW + row * (self.CARD_HEIGHT + gap)
            for column, item in enumerate(items):
                item.setGeometry(left + column * (card_width + gap), top, card_width, self.CARD_HEIGHT)
        rows = (len(self.buttons) + columns - 1) // columns
        height = self.FIRST_ROW + rows * (self.CARD_HEIGHT + gap)
        if self.height() != height:
            self.setFixedHeight(height)
        super().resizeEvent(event)

    def select(self,ident):
        for item in self.buttons:
            item.select(item.person['id']==ident)

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor(tint(self.faculty['color'],.97)))
        p.setPen(QPen(QColor(tint(self.faculty['color'],.75)),1))
        for x in range(14,self.width(),22):
            for y in range(14,self.height(),22):
                p.drawPoint(x,y)
        p.setPen(QPen(QColor(self.faculty['color']),2,Qt.PenStyle.DashLine))
        centre=QPointF(self.mark.geometry().center())
        for item in self.buttons:
            target=QPointF(item.geometry().center())
            path=QPainterPath(centre)
            path.cubicTo(QPointF(target.x(),centre.y()),QPointF(centre.x(),target.y()),target)
            p.drawPath(path)


class ResearchMap(QWidget):
    def __init__(self,person,accent):
        super().__init__()
        self.person,self.accent=person,accent
        self.setMinimumHeight(175)
        self.setAccessibleName('Specjalizacje: '+', '.join(person['themes']))

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area=QRectF(self.rect()).adjusted(1,1,-1,-1)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(tint(self.accent,.94)))
        p.drawRoundedRect(area,14,14)
        centre=QPointF(area.width()/2,area.height()/2)
        positions=[QPointF(area.width()*.18,area.height()*.26),
                   QPointF(area.width()*.82,area.height()*.26),
                   QPointF(area.width()*.50,area.height()*.84)]
        p.setPen(QPen(QColor(tint(self.accent,.60)),2))
        for target in positions: p.drawLine(centre,target)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(self.accent))
        p.drawEllipse(centre,27,27)
        p.setPen(QColor('white')); p.setFont(QFont('Segoe UI',10,QFont.Weight.Bold))
        p.drawText(QRectF(centre.x()-28,centre.y()-18,56,36),Qt.AlignmentFlag.AlignCenter,'POMYSŁ')
        for word,target in zip(self.person['themes'],positions):
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('white'))
            rect=QRectF(target.x()-63,target.y()-20,126,40)
            p.drawRoundedRect(rect,12,12)
            p.setPen(QColor(self.accent).darker(140)); p.setFont(QFont('Segoe UI',10,QFont.Weight.DemiBold))
            p.drawText(rect.adjusted(5,2,-5,-2),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,word)


class LecturerExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.data=catalog()
        self.faculty='WIiM'; self.person='lena'
        self.root=box(self,margins=0,spacing=18)
        self.root.addWidget(label('Poznaj wykładowców',30,NAVY,True))
        self.root.addWidget(label('Wybierz wydział i odkryj ludzi, pomysły oraz zajęcia, które mogą Cię zainspirować.',14,MUTED,wrap=True))
        self.root.addWidget(label('Profile i przykłady zajęć są fikcyjne.',11,MUTED,wrap=True))
        self.faculty_host=QWidget()
        self.faculty_grid=QGridLayout(self.faculty_host)
        self.faculty_grid.setContentsMargins(0,0,0,0); self.faculty_grid.setSpacing(10)
        self.faculty_buttons=[]
        self.faculty_group=QButtonGroup(self)
        for faculty in self.data['faculties']:
            item=QPushButton(); item.setCheckable(True)
            item.setObjectName('faculty-'+faculty['code'])
            self.faculty_group.addButton(item)
            item.setAccessibleName(faculty['name'])
            item.setToolTip(faculty['name'])
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            item.setMinimumWidth(74)
            item.setFixedHeight(70)
            line=box(item,margins=4,spacing=0)
            mark=ProgrammeMark({'name':'','faculty':faculty['code'],'color':faculty['color']}, compact=True)
            mark.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            line.addWidget(mark, 0, Qt.AlignmentFlag.AlignHCenter)
            code=label(faculty['code'],12,QColor(faculty['color']).darker(130).name(),True)
            code.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            line.addWidget(code, 0, Qt.AlignmentFlag.AlignHCenter)
            item.clicked.connect(lambda checked=False,f=faculty:self.choose_faculty(f['code']))
            self.faculty_buttons.append((faculty,item))
        self.root.addWidget(self.faculty_host)
        self.body=box(horizontal=True,spacing=16)
        self.root.addLayout(self.body)
        links=box(horizontal=True)
        links.addWidget(label('Poznaj również rzeczywisty dorobek naukowy w publicznych źródłach.',12,MUTED,wrap=True),1)
        links.addWidget(website('RAD-on / POL-on',self.data['repository']['url']))
        self.root.addLayout(links)
        self.columns=0; self.reflow()
        self.build_faculty()

    def resizeEvent(self,event):
        self.reflow()
        super().resizeEvent(event)

    def reflow(self):
        cols=8 if self.width()>=662 else 4
        if cols==self.columns: return
        for i in range(max(self.columns, cols)):
            self.faculty_grid.setColumnStretch(i, int(i < cols))
        self.columns=cols
        for i,(_,item) in enumerate(self.faculty_buttons):
            self.faculty_grid.addWidget(item,i//cols,i%cols)

    def choose_faculty(self,code):
        if code==self.faculty: return
        self.faculty=code
        self.person=next(p['id'] for p in self.data['people'] if p['faculty']==code)
        self.build_faculty()

    def build_faculty(self):
        while self.body.count():
            old=self.body.takeAt(0).widget()
            old.hide(); old.deleteLater()
        faculty=next(f for f in self.data['faculties'] if f['code']==self.faculty)
        for f,item in self.faculty_buttons:
            item.setChecked(f['code']==self.faculty)
            item.setStyleSheet(
                f"QPushButton {{ background:{tint(f['color'],.94)}; border:2px solid #DFE7F0; "
                "border-radius:10px; padding:0; min-height:66px; max-height:66px; }"
                f"QPushButton:hover, QPushButton:checked {{ border-color:{f['color']}; }}"
                "QPushButton:focus { border-color:#DDA52A; }"
            )
        panel,layout=card(18)
        layout.addWidget(label(faculty['name'],18,NAVY,True,True))
        layout.addWidget(label('Kliknij sylwetkę, aby przybliżyć profil.',12,MUTED,wrap=True))
        people=[p for p in self.data['people'] if p['faculty']==self.faculty]
        self.map=PeopleMap(faculty,people,self.person,self.choose_person)
        layout.addWidget(self.map)
        self.body.addWidget(panel,5,Qt.AlignmentFlag.AlignTop)
        self.detail,self.detail_layout=card(20)
        self.detail.setObjectName('lecturer-detail')
        self.detail.setStyleSheet('QFrame#lecturer-detail { background:white; border:1px solid #DFE7F0; border-top:5px solid '+faculty['color']+'; border-radius:14px; }')
        self.body.addWidget(self.detail,6,Qt.AlignmentFlag.AlignTop)
        self.show_person(False)

    def choose_person(self,ident):
        if ident==self.person: return
        self.person=ident; self.map.select(ident); self.show_person(True)

    def show_person(self,animate):
        layout=self.detail_layout
        while layout.count():
            item=layout.takeAt(0)
            if item.widget():
                item.widget().hide(); item.widget().deleteLater()
        person=next(p for p in self.data['people'] if p['id']==self.person)
        faculty=next(f for f in self.data['faculties'] if f['code']==self.faculty)
        accent=faculty['color']
        header=QWidget(); row=box(header,horizontal=True,margins=0)
        # Animate the portrait inside its fixed bounds. An opacity effect on the
        # whole detail panel can keep a clipped render when it is partly scrolled out.
        row.addWidget(Portrait(person,accent,animate),0,Qt.AlignmentFlag.AlignTop)
        titles=box(spacing=7)
        name=label(person['name'],22,NAVY,True,True); name.setObjectName('lecturer-name')
        titles.addWidget(name)
        titles.addWidget(label(person['focus'],13,accent,True,True))
        row.addLayout(titles,1); layout.addWidget(header)
        layout.addWidget(label(person['bio'],13,MUTED,wrap=True))
        layout.addWidget(label('Spotkamy się na zajęciach',16,NAVY,True))
        layout.addWidget(label(person['course'],14,accent,True,True))
        layout.addWidget(label(person['program']+' · I stopień · semestr '+str(person['semester']),12,MUTED,wrap=True))
        layout.addWidget(label(person['exercise'],13,wrap=True))
        layout.addWidget(ResearchMap(person,accent))
        for work in person['works']:
            layout.addWidget(label(work['kind']+' · dorobek przykładowy',11,MUTED,wrap=True))
            layout.addWidget(label(work['title'],13,NAVY,True,True))
        message=QWidget(); quote=box(message,margins=14,spacing=5)
        message.setStyleSheet('background:'+tint(accent,.93)+'; border-radius:12px;')
        quote.addWidget(label('Kilka słów do Ciebie',12,accent,True))
        quote.addWidget(label('„'+person['quote']+'”',14,NAVY,wrap=True))
        layout.addWidget(message)
        layout.addStretch()
