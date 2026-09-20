"""Wiederverwendbare Glass-Widgets: Hintergrund, Panels, animierte Buttons, Segment-Umschalter, Dialog-Basis."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import (QEasingCurve, QEvent, QObject, QPoint, QPointF, QRectF, QSize, Qt,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QCursor, QLinearGradient, QPainter, QPainterPath,
                           QRadialGradient)
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

import platform_utils as pu
from ui import style
from ui.icons import draw_glyph

RADIUS = 20
NATIVE_BLUR = True    # wird von main.py aus den Einstellungen gesetzt
NATIVE_STYLE = "blur"


def try_native_blur(widget, background: "GlassBackground", radius: float = RADIUS) -> None:
    """Aktiviert einmalig natives Blur für ein Fenster; bei Fehlschlag bleibt der QSS-Look."""
    if getattr(widget, "_blur_tried", False):
        return
    widget._blur_tried = True
    if NATIVE_BLUR:
        background.blur_active = pu.apply_native_blur(widget, radius=radius, style=NATIVE_STYLE)
        background.update()


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t), int(a.alpha() + (b.alpha() - a.alpha()) * t))


def paint_liquid_glass(p: QPainter, r: QRectF, radius: float, fill: int = 10,
                       tint: Optional[QColor] = None, highlight: float = 1.0, glow: float = 0.0,
                       shadow: float = 0.0) -> None:
    """Ruhige Glasfläche: milchiger Körper mit sanfter Tiefe – ohne Lichtkanten, Glanz oder Glow.

    highlight/glow bleiben aus Kompatibilitätsgründen Parameter, wirken aber nur noch dezent auf die Tiefe.
    """
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)

    if shadow > 0:  # sehr weicher Schatten für Tiefe
        for i in range(1, 6):
            p.setBrush(QColor(0, 0, 10, int(shadow * 9 / i)))
            p.drawRoundedRect(r.adjusted(-i * 0.6, i * 0.4 + 1, i * 0.6, i * 1.1 + 1), radius + i, radius + i)

    body = QLinearGradient(r.topLeft(), r.bottomLeft())
    body.setColorAt(0, QColor(255, 255, 255, min(255, fill + int(5 * highlight))))
    body.setColorAt(1, QColor(255, 255, 255, max(0, fill - 3)))
    p.fillPath(path, body)
    if tint is not None:
        p.fillPath(path, tint)
    p.restore()


class GlassBackground(QWidget):
    """Fensterhintergrund: Dunkelblau/Lila-Tönung mit weichen Farbflächen über echtem Glas-Blur."""

    def __init__(self, parent=None, radius: int = RADIUS):
        super().__init__(parent)
        self.setObjectName("Root")
        self.radius = radius
        self.blur_active = False
        self.rounded = True

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = self.radius if self.rounded else 0
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        p.setClipPath(path)

        # mit nativem Glas nur leicht tönen → Desktop scheint durch
        alpha = 120 if self.blur_active else 246
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        for pos, c in ((0.0, style.BG_TOP), (0.5, style.BG_MID), (1.0, style.BG_BOTTOM)):
            c = QColor(c)
            c.setAlpha(alpha)
            g.setColorAt(pos, c)
        p.fillPath(path, g)

        span = max(r.width(), r.height())
        for cx, cy, rad_f, col, a in ((0.0, 0.0, 0.7, QColor(60, 30, 140), 40),
                                      (1.0, 1.0, 0.8, QColor(90, 30, 160), 45)):
            glow = QRadialGradient(QPointF(r.width() * cx, r.height() * cy), span * rad_f)
            c0 = QColor(col); c0.setAlpha(a)
            c1 = QColor(col); c1.setAlpha(0)
            glow.setColorAt(0, c0)
            glow.setColorAt(1, c1)
            p.fillPath(path, glow)
        p.setClipping(False)


class GlassPanel(QWidget):
    """Schwebende Liquid-Glass-Fläche."""

    def __init__(self, parent=None, radius: int = 20, alpha: int = 10, shadow: float = 1.0):
        super().__init__(parent)
        self.radius, self.alpha, self.shadow = radius, alpha, shadow
        self.setAttribute(Qt.WA_StyledBackground, False)

    def paintEvent(self, _):
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(3, 1, -3, -5 if self.shadow else -1)
        paint_liquid_glass(p, r, self.radius, self.alpha, shadow=self.shadow * 0.6)


class GlassButton(QPushButton):
    """Button mit weichen, animierten Hover-/Press-Übergängen.

    variant: "glass" (Standard), "primary" (Verlauf), "danger", "ghost"
    """

    def __init__(self, text: str = "", icon_name: Optional[str] = None, variant: str = "glass",
                 parent=None, compact: bool = False):
        super().__init__(text, parent)
        self.icon_name = icon_name
        self.variant = variant
        self.compact = compact
        self._hover = 0.0
        self._press = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self._anim = QVariantAnimation(self, duration=180, easingCurve=QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_hover)
        self._panim = QVariantAnimation(self, duration=120, easingCurve=QEasingCurve.OutCubic)
        self._panim.valueChanged.connect(self._set_press)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

    def _set_hover(self, v):
        self._hover = float(v)
        self.update()

    def _set_press(self, v):
        self._press = float(v)
        self.update()

    def _animate(self, anim, start, end):
        anim.stop()
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.start()

    def enterEvent(self, e):
        self._animate(self._anim, self._hover, 1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate(self._anim, self._hover, 0.0)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._animate(self._panim, self._press, 1.0)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._animate(self._panim, self._press, 0.0)
        super().mouseReleaseEvent(e)

    def sizeHint(self):
        fm = self.fontMetrics()
        h = 32 if self.compact else 38
        icon_w = 18 + (6 if self.text() else 0) if self.icon_name else 0
        text_w = fm.horizontalAdvance(self.text()) if self.text() else 0
        pad = 12 if not self.text() else (14 if self.compact else 18)
        w = max(h, icon_w + text_w + pad * 2 - (6 if not self.text() and self.icon_name else 0))
        return QSize(w, h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        rad = r.height() / 2  # Kapselform
        h, pr = self._hover, self._press
        enabled = self.isEnabled()
        checked = self.isCheckable() and self.isChecked()

        if pr:
            p.setOpacity(1.0 - 0.15 * pr)
        if not enabled:
            p.setOpacity(0.4)

        if self.variant == "primary" or checked:
            # milchiges Glas mit lila Schimmer statt kräftiger Farbfläche
            paint_liquid_glass(p, r, rad, 30 + int(14 * h), QColor(150, 105, 235, 70 + int(30 * h)))
        elif self.variant == "danger":
            paint_liquid_glass(p, r, rad, 8, QColor(248, 113, 113, 50 + int(60 * h)), highlight=1.0)
        elif self.variant == "ghost":
            if h > 0:
                paint_liquid_glass(p, r, rad, int(16 * h), highlight=h)
        else:
            paint_liquid_glass(p, r, rad, 12 + int(12 * h))

        color = QColor(255, 255, 255) if enabled else style.TEXT_MUTED
        fm = self.fontMetrics()
        text = self.text()
        icon_size = 16 if not self.compact else 14
        total = (icon_size if self.icon_name else 0) + (6 if self.icon_name and text else 0) + \
                (fm.horizontalAdvance(text) if text else 0)
        x = r.center().x() - total / 2
        if self.icon_name:
            draw_glyph(p, self.icon_name, QRectF(x, r.center().y() - icon_size / 2, icon_size, icon_size), color)
            x += icon_size + (6 if text else 0)
        if text:
            p.setPen(color)
            f = p.font()
            f.setWeight(f.Weight.DemiBold if self.variant == "primary" else f.Weight.Medium)
            p.setFont(f)
            p.drawText(QRectF(x, r.top(), r.right() - x, r.height()), Qt.AlignVCenter | Qt.AlignLeft, text)


class SegmentedToggle(QWidget):
    """Segment-Umschalter (z. B. Video | Audio) mit gleitendem Verlaufs-Indikator."""
    changed = Signal(str)

    def __init__(self, options: List[tuple], parent=None, icons: Optional[List[str]] = None):
        super().__init__(parent)
        self.options = options  # [(key, label)]
        self.icons = icons or [None] * len(options)
        self._index = 0
        self._pos = 0.0
        self._anim = QVariantAnimation(self, duration=220, easingCurve=QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        self.setMinimumWidth(90 * len(options))

    def _on_anim(self, v):
        self._pos = float(v)
        self.update()

    def value(self) -> str:
        return self.options[self._index][0]

    def setValue(self, key: str, animate: bool = False) -> None:
        for i, (k, _) in enumerate(self.options):
            if k == key:
                self._select(i, animate, emit=False)

    def _select(self, i: int, animate: bool = True, emit: bool = True) -> None:
        if i == self._index and emit:
            return
        self._index = i
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(float(i))
            self._anim.start()
        else:
            self._pos = float(i)
            self.update()
        if emit:
            self.changed.emit(self.value())

    def mousePressEvent(self, e):
        seg = self.width() / len(self.options)
        self._select(min(len(self.options) - 1, int(e.position().x() // seg)))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = r.height() / 2
        paint_liquid_glass(p, r, rad, 6, QColor(0, 0, 20, 70))
        seg = (r.width() - 6) / len(self.options)
        ind = QRectF(r.left() + 3 + self._pos * seg, r.top() + 3, seg, r.height() - 6)
        paint_liquid_glass(p, ind, ind.height() / 2, 34, QColor(150, 105, 235, 75))
        fm = self.fontMetrics()
        for i, (_, label) in enumerate(self.options):
            cell = QRectF(r.left() + 3 + i * seg, r.top(), seg, r.height())
            active = abs(self._pos - i) < 0.5
            color = QColor(255, 255, 255) if active else style.TEXT_MUTED
            icon_name = self.icons[i]
            tw = fm.horizontalAdvance(label)
            total = tw + (20 if icon_name else 0)
            x = cell.center().x() - total / 2
            if icon_name:
                draw_glyph(p, icon_name, QRectF(x, cell.center().y() - 7, 14, 14), color)
                x += 20
            p.setPen(color)
            p.drawText(QRectF(x, cell.top(), tw + 2, cell.height()), Qt.AlignVCenter, label)


class FramelessResizer(QObject):
    """Ermöglicht Größenänderung rahmenloser Fenster über die Ränder (plattformübergreifend)."""
    MARGIN = 6

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.window = window
        self._cursor_set = False
        QApplication.instance().installEventFilter(self)

    def _edges(self, gpos: QPoint):
        w = self.window
        if w.isMaximized() or w.isFullScreen():
            return Qt.Edges()
        pos = w.mapFromGlobal(gpos)
        m = self.MARGIN
        edges = Qt.Edges()
        if pos.x() <= m:
            edges |= Qt.LeftEdge
        elif pos.x() >= w.width() - m:
            edges |= Qt.RightEdge
        if pos.y() <= m:
            edges |= Qt.TopEdge
        elif pos.y() >= w.height() - m:
            edges |= Qt.BottomEdge
        return edges

    @staticmethod
    def _cursor_for(edges):
        l, r = bool(edges & Qt.LeftEdge), bool(edges & Qt.RightEdge)
        t, b = bool(edges & Qt.TopEdge), bool(edges & Qt.BottomEdge)
        if (l and t) or (r and b):
            return Qt.SizeFDiagCursor
        if (r and t) or (l and b):
            return Qt.SizeBDiagCursor
        if l or r:
            return Qt.SizeHorCursor
        return Qt.SizeVerCursor

    def eventFilter(self, obj, event):
        et = event.type()
        if et not in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.HoverMove):
            return False
        if not isinstance(obj, QWidget) or obj.window() is not self.window:
            return False
        edges = self._edges(QCursor.pos())
        if et in (QEvent.MouseMove, QEvent.HoverMove):
            if edges and not (event.buttons() if et == QEvent.MouseMove else False):
                if not self._cursor_set:
                    QApplication.setOverrideCursor(self._cursor_for(edges))
                    self._cursor_set = True
                else:
                    QApplication.changeOverrideCursor(self._cursor_for(edges))
            elif not edges and self._cursor_set:
                QApplication.restoreOverrideCursor()
                self._cursor_set = False
            return False
        if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton and edges:
            handle = self.window.windowHandle()
            if handle and handle.startSystemResize(edges):
                return True
        return False


class GlassDialog(QDialog):
    """Rahmenloser Dialog im Glass-Stil mit eigener Titelzeile (ziehbar)."""

    def __init__(self, title: str, parent=None, width: int = 520):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(width)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.bg = GlassBackground(self)
        outer.addWidget(self.bg)
        lay = QVBoxLayout(self.bg)
        lay.setContentsMargins(24, 18, 24, 22)
        lay.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(10)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("DialogTitle")
        close = GlassButton(icon_name="close", variant="ghost", compact=True)
        close.setFixedSize(28, 28)
        close.clicked.connect(self.reject)
        if pu.IS_MAC:
            head.addWidget(close)
            head.addWidget(self.title_label, 1)
        else:
            head.addWidget(self.title_label, 1)
            head.addWidget(close)
        lay.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        lay.addLayout(self.body, 1)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(10)
        self.buttons.addStretch(1)
        lay.addLayout(self.buttons)
        self._drag: Optional[QPoint] = None

    def add_button(self, text: str, variant: str = "glass", role: Optional[str] = None,
                   icon_name: Optional[str] = None) -> GlassButton:
        b = GlassButton(text, icon_name=icon_name, variant=variant)
        if role == "accept":
            b.clicked.connect(self.accept)
            b.setDefault(True)
        elif role == "reject":
            b.clicked.connect(self.reject)
        # macOS: primäre Aktion rechts außen; Windows/Linux ebenfalls üblich
        self.buttons.addWidget(b)
        return b

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.position().y() < 56:
            handle = self.windowHandle()
            if handle and handle.startSystemMove():
                return
        super().mousePressEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        try_native_blur(self, self.bg)
        if self.parentWidget() and self.parentWidget().isVisible():
            pg = self.parentWidget().window().frameGeometry()
            self.move(pg.center() - self.rect().center())


def message(parent, title: str, text: str, buttons=(("OK", "primary", "ok"),), width: int = 460) -> str:
    """Glass-Messagebox. buttons: [(Text, Variante, Schlüssel)] → gibt den Schlüssel zurück ('' bei Abbruch)."""
    dlg = GlassDialog(title, parent, width)
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lbl.setMinimumWidth(width - 60)
    dlg.body.addWidget(lbl)
    result = {"key": ""}
    for label, variant, key in buttons:
        b = dlg.add_button(label, variant)

        def done(_=False, k=key):
            result["key"] = k
            dlg.accept()
        b.clicked.connect(done)
        if variant == "primary":
            b.setDefault(True)
    dlg.exec()
    return result["key"]
