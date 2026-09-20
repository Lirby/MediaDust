"""Vektor-Icons, zur Laufzeit mit QPainter gezeichnet (keine Asset-Dateien nötig)."""
from __future__ import annotations

import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (QBrush, QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPainterPathStroker, QPen, QPixmap, QRadialGradient)

from ui import style


def _pen(color: QColor, w: float) -> QPen:
    pen = QPen(color, w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def draw_glyph(p: QPainter, name: str, r: QRectF, color: QColor) -> None:
    """Zeichnet ein Glyph in das Rechteck r (quadratisch empfohlen)."""
    s = min(r.width(), r.height())
    cx, cy = r.center().x(), r.center().y()
    u = s / 16.0
    w = max(1.4, 1.6 * u)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(_pen(color, w))
    p.setBrush(Qt.NoBrush)

    def pt(x, y):
        return QPointF(cx + x * u, cy + y * u)

    if name == "plus":
        p.drawLine(pt(-5, 0), pt(5, 0)); p.drawLine(pt(0, -5), pt(0, 5))
    elif name == "play":
        path = QPainterPath(pt(-3.5, -5.5)); path.lineTo(pt(5.5, 0)); path.lineTo(pt(-3.5, 5.5)); path.closeSubpath()
        p.setBrush(color); p.drawPath(path)
    elif name == "pause":
        p.setBrush(color); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(pt(-5, -5.5), pt(-1.5, 5.5)), u, u)
        p.drawRoundedRect(QRectF(pt(1.5, -5.5), pt(5, 5.5)), u, u)
    elif name == "stop":
        p.setBrush(color); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(pt(-4.5, -4.5), pt(4.5, 4.5)), 1.5 * u, 1.5 * u)
    elif name in ("close", "x"):
        p.drawLine(pt(-4.5, -4.5), pt(4.5, 4.5)); p.drawLine(pt(4.5, -4.5), pt(-4.5, 4.5))
    elif name == "minimize":
        p.drawLine(pt(-5, 0), pt(5, 0))
    elif name == "maximize":
        p.drawRoundedRect(QRectF(pt(-4.5, -4.5), pt(4.5, 4.5)), u, u)
    elif name == "trash":
        p.drawLine(pt(-6, -4), pt(6, -4))
        p.drawLine(pt(-2, -4), pt(-2, -6)); p.drawLine(pt(-2, -6), pt(2, -6)); p.drawLine(pt(2, -6), pt(2, -4))
        path = QPainterPath(pt(-4.5, -4)); path.lineTo(pt(-3.5, 6)); path.lineTo(pt(3.5, 6)); path.lineTo(pt(4.5, -4))
        p.drawPath(path)
        p.drawLine(pt(-1, -1), pt(-1, 3.5)); p.drawLine(pt(1.5, -1), pt(1.5, 3.5))
    elif name == "folder":
        path = QPainterPath(pt(-6.5, -4.5)); path.lineTo(pt(-2, -4.5)); path.lineTo(pt(-0.5, -2.8))
        path.lineTo(pt(6.5, -2.8)); path.lineTo(pt(6.5, 5)); path.lineTo(pt(-6.5, 5)); path.closeSubpath()
        p.drawPath(path)
    elif name == "gear":
        p.drawEllipse(pt(0, 0), 2.2 * u, 2.2 * u)
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QPointF(cx + math.cos(a) * 4.4 * u, cy + math.sin(a) * 4.4 * u),
                       QPointF(cx + math.cos(a) * 6.3 * u, cy + math.sin(a) * 6.3 * u))
        p.drawEllipse(pt(0, 0), 4.4 * u, 4.4 * u)
    elif name == "clipboard":
        p.drawRoundedRect(QRectF(pt(-5, -5), pt(5, 6.5)), 1.5 * u, 1.5 * u)
        p.drawRoundedRect(QRectF(pt(-2.5, -6.5), pt(2.5, -3.8)), u, u)
        p.drawLine(pt(-2.5, 0), pt(2.5, 0)); p.drawLine(pt(-2.5, 3), pt(1, 3))
    elif name == "retry":
        p.drawArc(QRectF(pt(-5.5, -5.5), pt(5.5, 5.5)), 60 * 16, 290 * 16)
        path = QPainterPath(pt(2, -6.8)); path.lineTo(pt(5.4, -4.9)); path.lineTo(pt(2.6, -2.2))
        p.drawPath(path)
    elif name == "up":
        p.drawLine(pt(0, 5.5), pt(0, -5)); p.drawLine(pt(-4, -1.5), pt(0, -5.5)); p.drawLine(pt(4, -1.5), pt(0, -5.5))
    elif name == "down":
        p.drawLine(pt(0, -5.5), pt(0, 5)); p.drawLine(pt(-4, 1.5), pt(0, 5.5)); p.drawLine(pt(4, 1.5), pt(0, 5.5))
    elif name == "download":
        p.drawLine(pt(0, -6), pt(0, 2.5)); p.drawLine(pt(-3.5, -1), pt(0, 2.5)); p.drawLine(pt(3.5, -1), pt(0, 2.5))
        p.drawLine(pt(-5.5, 6), pt(5.5, 6))
    elif name == "sweep":
        p.drawLine(pt(-5.5, 0.5), pt(-2, 4)); p.drawLine(pt(-2, 4), pt(5.5, -4))
    elif name == "link":
        p.drawRoundedRect(QRectF(pt(-7, -2.5), pt(0.5, 2.5)), 2.5 * u, 2.5 * u)
        p.drawRoundedRect(QRectF(pt(-0.5, -2.5), pt(7, 2.5)), 2.5 * u, 2.5 * u)
    elif name == "music":
        p.drawLine(pt(-2, 4), pt(-2, -5)); p.drawLine(pt(-2, -5), pt(5, -6.5)); p.drawLine(pt(5, -6.5), pt(5, 2.5))
        p.setBrush(color)
        p.drawEllipse(pt(-4, 4), 2 * u, 1.6 * u); p.drawEllipse(pt(3, 2.8), 2 * u, 1.6 * u)
    elif name == "video":
        p.drawRoundedRect(QRectF(pt(-7, -4.5), pt(3, 4.5)), 1.5 * u, 1.5 * u)
        path = QPainterPath(pt(3, -1)); path.lineTo(pt(7, -3.5)); path.lineTo(pt(7, 3.5)); path.lineTo(pt(3, 1))
        p.drawPath(path)
    elif name == "file":
        path = QPainterPath(pt(-4.5, -6.5)); path.lineTo(pt(1.5, -6.5)); path.lineTo(pt(4.5, -3.5))
        path.lineTo(pt(4.5, 6.5)); path.lineTo(pt(-4.5, 6.5)); path.closeSubpath()
        p.drawPath(path)
    elif name == "star":
        draw_sparkle(p, QPointF(cx, cy), 6.5 * u, color)
    p.restore()


def draw_sparkle(p: QPainter, c: QPointF, radius: float, color: QColor) -> None:
    """Vierzackiger Funkel-Stern."""
    k = radius * 0.22
    path = QPainterPath(QPointF(c.x(), c.y() - radius))
    path.quadTo(QPointF(c.x() + k, c.y() - k), QPointF(c.x() + radius, c.y()))
    path.quadTo(QPointF(c.x() + k, c.y() + k), QPointF(c.x(), c.y() + radius))
    path.quadTo(QPointF(c.x() - k, c.y() + k), QPointF(c.x() - radius, c.y()))
    path.quadTo(QPointF(c.x() - k, c.y() - k), QPointF(c.x(), c.y() - radius))
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(path)
    p.restore()


@lru_cache(maxsize=128)
def icon(name: str, color: str = "#eaecfa", size: int = 32) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_glyph(p, name, QRectF(2, 2, size - 4, size - 4), QColor(color))
    p.end()
    return QIcon(pm)


def _soft_glow(shape: QPainterPath, size: QSize, color: QColor, radius_px: float) -> QImage:
    """Weicher Glow um eine Form (Downsample-Blur, ohne Zusatzbibliotheken)."""
    img = QImage(size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    q = QPainter(img)
    q.setRenderHint(QPainter.Antialiasing)
    q.setPen(QPen(color, radius_px * 0.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    q.setBrush(color)
    q.drawPath(shape)
    q.end()
    factor = max(2, int(radius_px))
    small = img.scaled(max(1, size.width() // factor), max(1, size.height() // factor),
                       Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    small = small.scaled(max(1, small.width() // 2 + 1), max(1, small.height() // 2 + 1),
                         Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return small.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


_LOGO_IMAGE = None


def _logo_image():
    """assets/icon.png, auf die sichtbare Fläche zugeschnitten (ohne transparenten Rand)."""
    global _LOGO_IMAGE
    if _LOGO_IMAGE is None:
        from platform_utils import resource_path
        img = QImage(str(resource_path("assets/icon.png")))
        if img.isNull():
            _LOGO_IMAGE = False
        else:
            img = img.convertToFormat(QImage.Format_ARGB32)
            w, h = img.width(), img.height()
            step = max(1, w // 300)
            xs = [x for x in range(0, w, step) if img.pixelColor(x, h // 2).alpha() > 40]
            ys = [y for y in range(0, h, step) if img.pixelColor(w // 2, y).alpha() > 40]
            if xs and ys:
                side = max(xs[-1] - xs[0], ys[-1] - ys[0])
                cx, cy = (xs[0] + xs[-1]) // 2, (ys[0] + ys[-1]) // 2
                img = img.copy(cx - side // 2, cy - side // 2, side, side)
            _LOGO_IMAGE = img
    return _LOGO_IMAGE or None


def draw_logo(p: QPainter, r: QRectF) -> None:
    """App-Logo: bevorzugt das Bild aus assets/icon.png, sonst die Vektor-Version."""
    img = _logo_image()
    if img is not None:
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawImage(r, img)
        p.restore()
        return
    _draw_vector_logo(p, r)


def _draw_vector_logo(p: QPainter, r: QRectF) -> None:
    """Vektor-Logo (Fallback, auch für tools/make_icon.py)."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    s = r.width()
    rad = s * 0.24
    body = QPainterPath()
    body.addRoundedRect(r, rad, rad)

    # Lila Glasgrund
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0.0, QColor(122, 92, 240))
    g.setColorAt(0.45, QColor(88, 50, 196))
    g.setColorAt(1.0, QColor(46, 22, 120))
    p.fillPath(body, g)
    p.setClipPath(body)
    inner = QRadialGradient(QPointF(r.center().x(), r.top() + s * 0.62), s * 0.55)
    inner.setColorAt(0, QColor(170, 130, 255, 120))
    inner.setColorAt(1, QColor(170, 130, 255, 0))
    p.fillPath(body, inner)
    # Glas-Lichtstreifen diagonal
    p.save()
    p.translate(r.left() + s * 0.55, r.top())
    p.rotate(32)
    streak = QLinearGradient(0, 0, s * 0.22, 0)
    streak.setColorAt(0, QColor(255, 255, 255, 0))
    streak.setColorAt(0.5, QColor(255, 255, 255, 34))
    streak.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillRect(QRectF(0, -s, s * 0.22, s * 3), streak)
    p.restore()
    # Aero-Glanz obere Hälfte
    top = QPainterPath()
    top.addRoundedRect(QRectF(r.left(), r.top(), s, s * 0.52), rad, rad)
    sheen = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + s * 0.52))
    sheen.setColorAt(0, QColor(255, 255, 255, 95))
    sheen.setColorAt(1, QColor(255, 255, 255, 8))
    p.fillPath(top, sheen)
    p.setClipping(False)
    # Glaskanten
    p.setBrush(Qt.NoBrush)
    edge = QLinearGradient(r.topLeft(), r.bottomLeft())
    edge.setColorAt(0, QColor(255, 255, 255, 190))
    edge.setColorAt(0.5, QColor(220, 200, 255, 60))
    edge.setColorAt(1, QColor(200, 170, 255, 120))
    p.setPen(QPen(edge, max(1.0, s * 0.012)))
    inset = s * 0.012
    p.drawRoundedRect(r.adjusted(inset, inset, -inset, -inset), rad - inset, rad - inset)

    # Leuchtender Pfeil (weich, hell-lavendel)
    cx = r.center().x()
    line = QPainterPath(QPointF(cx, r.top() + s * 0.24))
    line.lineTo(QPointF(cx, r.top() + s * 0.58))
    line.moveTo(QPointF(cx - s * 0.155, r.top() + s * 0.44))
    line.lineTo(QPointF(cx, r.top() + s * 0.595))
    line.lineTo(QPointF(cx + s * 0.155, r.top() + s * 0.44))
    line.moveTo(QPointF(r.left() + s * 0.30, r.top() + s * 0.72))
    line.lineTo(QPointF(r.right() - s * 0.30, r.top() + s * 0.72))
    stroker = QPainterPathStroker()
    stroker.setWidth(s * 0.095)
    stroker.setCapStyle(Qt.RoundCap)
    stroker.setJoinStyle(Qt.RoundJoin)
    glyph = stroker.createStroke(line).simplified()

    if s >= 32:
        full = QSize(int(r.right() + s * 0.1 + 1), int(r.bottom() + s * 0.1 + 1))
        glow = _soft_glow(glyph, full, QColor(190, 170, 255, 210), max(2.0, s * 0.05))
        p.drawImage(QRectF(0, 0, full.width(), full.height()), glow)
    fill = QLinearGradient(QPointF(cx, r.top() + s * 0.2), QPointF(cx, r.top() + s * 0.78))
    fill.setColorAt(0, QColor(250, 250, 255))
    fill.setColorAt(1, QColor(214, 206, 255))
    p.setPen(Qt.NoPen)
    p.fillPath(glyph, fill)

    # Funkeln wie im Vorbild: ein großer Stern oben rechts, kleine verstreut
    white = QColor(255, 255, 255)
    stars = [(0.77, 0.24, 0.075), (0.23, 0.25, 0.03), (0.67, 0.14, 0.022), (0.84, 0.48, 0.026),
             (0.19, 0.55, 0.032), (0.76, 0.82, 0.03), (0.27, 0.84, 0.022), (0.60, 0.86, 0.018)]
    for x, y, size in stars:
        c = QPointF(r.left() + s * x, r.top() + s * y)
        if s >= 32:
            halo = QRadialGradient(c, s * size * 1.8)
            halo.setColorAt(0, QColor(200, 180, 255, 150))
            halo.setColorAt(1, QColor(200, 180, 255, 0))
            p.setBrush(halo)
            p.drawEllipse(c, s * size * 1.8, s * size * 1.8)
        draw_sparkle(p, c, s * size, white)
    p.setBrush(QColor(230, 220, 255, 170))
    for x, y in ((0.36, 0.16), (0.88, 0.66), (0.14, 0.40), (0.45, 0.88)):
        p.drawEllipse(QPointF(r.left() + s * x, r.top() + s * y), s * 0.008, s * 0.008)
    p.restore()


def app_icon() -> QIcon:
    from platform_utils import resource_path
    png = resource_path("assets/icon.png")
    if png.exists():
        return QIcon(str(png))
    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_logo(p, QRectF(16, 16, 224, 224))
    p.end()
    return QIcon(pm)


def accent_gradient(rect: QRectF, horizontal: bool = True) -> QBrush:
    end = rect.topRight() if horizontal else rect.bottomLeft()
    g = QLinearGradient(rect.topLeft(), end)
    g.setColorAt(0.0, style.ACCENT_1)
    g.setColorAt(0.6, style.ACCENT_2)
    g.setColorAt(1.0, style.ACCENT_3)
    return QBrush(g)
