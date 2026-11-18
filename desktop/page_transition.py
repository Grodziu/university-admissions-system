from math import ceil

from PySide6.QtCore import QCoreApplication, QEasingCurve, QEvent, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from .widgets import PAGE_BACKGROUND


class PageTransition(QWidget):
    """Reveal the new frozen page on an opaque surface above the stack."""

    def __init__(self, stack):
        super().__init__(stack)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.outgoing = self.incoming = None
        self.progress = 0.
        self.animation = QVariantAnimation(self, duration=360, easingCurve=QEasingCurve.Type.InOutCubic)
        self.animation.setStartValue(0.)
        self.animation.setEndValue(1.)
        self.animation.valueChanged.connect(self.set_progress)
        self.animation.finished.connect(self.finish)
        stack.installEventFilter(self)
        self.hide()

    @staticmethod
    def capture(widget):
        scale = widget.devicePixelRatioF()
        frame = QPixmap(ceil(widget.width() * scale), ceil(widget.height() * scale))
        frame.setDevicePixelRatio(scale)
        frame.fill(QColor(PAGE_BACKGROUND))
        widget.render(frame)
        return frame

    def cover(self, previous):
        self.outgoing = self.capture(self if self.isVisible() else previous)
        self.animation.stop()
        self.incoming = None
        self.progress = 0.
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self.update()

    def reveal(self, page):
        # The scroll area can still have queued layout work after the page is shown.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
        self.incoming = self.capture(page)
        self.animation.start()

    def set_progress(self, value):
        self.progress = value
        self.update()

    def finish(self):
        self.animation.stop()
        self.hide()
        self.outgoing = self.incoming = None

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect())
        painter.fillRect(area, QColor(PAGE_BACKGROUND))
        if self.outgoing is not None:
            painter.drawPixmap(area, self.outgoing, QRectF(self.outgoing.rect()))
        if self.incoming is not None:
            reveal = QRectF(area)
            reveal.setWidth(area.width() * self.progress)
            painter.setClipRect(reveal)
            painter.drawPixmap(area, self.incoming, QRectF(self.incoming.rect()))
