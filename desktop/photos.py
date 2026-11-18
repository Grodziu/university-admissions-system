from PySide6.QtCore import QRectF


def draw_cover(painter, area, photo, *, horizontal_focus=.5):
    if photo.isNull() or area.isEmpty():
        return
    scale = max(area.width() / photo.width(), area.height() / photo.height())
    width, height = area.width() / scale, area.height() / scale
    source = QRectF((photo.width() - width) * horizontal_focus, (photo.height() - height) / 2, width, height)
    painter.drawPixmap(area, photo, source)
