"""Eigene Titelleiste für das rahmenlose Hauptfenster.

macOS: Ampel-Buttons links (Schließen/Minimieren/Zoomen) – wie Nutzer es gewohnt sind.
Windows/Linux: Minimieren/Maximieren/Schließen rechts.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QWidget

import platform_utils as pu
from ui import style
from ui.icons import draw_glyph, draw_logo


class TrafficLight(QAbstractButton):
    COLORS = {"close": QColor(255, 95, 87), "minimize": QColor(254, 188, 46), "maximize": QColor(40, 200, 64)}

    def __init__(self, kind: str, group: "TrafficLights"):
        super().__init__(group)
        self.kind = kind
        self.group = group
        self.setFixedSize(14, 14)
        self.setCursor(Qt.ArrowCursor)
        self.setToolTip({"close": "Schließen", "minimize": "Minimieren", "maximize": "Zoomen"}[kind])

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, 13, 13)
        active = self.window().isActiveWindow() or self.group.hovered
        color = self.COLORS[self.kind] if active else QColor(255, 255, 255, 45)
        if self.isDown():
            color = color.darker(125)
        p.setPen(QPen(color.darker(130), 0.6))
        p.setBrush(color)
        p.drawEllipse(r)
        if self.group.hovered:
            g = QColor(0, 0, 0, 150)
            p.setPen(QPen(g, 1.3, Qt.SolidLine, Qt.RoundCap))
            c = r.center()
            if self.kind == "close":
                p.drawLine(QPointF(c.x() - 3, c.y() - 3), QPointF(c.x() + 3, c.y() + 3))
                p.drawLine(QPointF(c.x() + 3, c.y() - 3), QPointF(c.x() - 3, c.y() + 3))
            elif self.kind == "minimize":
                p.drawLine(QPointF(c.x() - 3.5, c.y()), QPointF(c.x() + 3.5, c.y()))
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(g)
                p.drawPolygon([QPointF(c.x() - 3.2, c.y() - 3.2), QPointF(c.x() + 1.3, c.y() - 3.2),
                               QPointF(c.x() - 3.2, c.y() + 1.3)])
                p.drawPolygon([QPointF(c.x() + 3.2, c.y() + 3.2), QPointF(c.x() - 1.3, c.y() + 3.2),
                               QPointF(c.x() + 3.2, c.y() - 1.3)])


class TrafficLights(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.close_btn = TrafficLight("close", self)
        self.min_btn = TrafficLight("minimize", self)
        self.max_btn = TrafficLight("maximize", self)
        for b in (self.close_btn, self.min_btn, self.max_btn):
            lay.addWidget(b)

    def enterEvent(self, e):
        self.hovered = True
        self.update_children()

    def leaveEvent(self, e):
        self.hovered = False
        self.update_children()

    def update_children(self):
        for b in (self.close_btn, self.min_btn, self.max_btn):
            b.update()


class CaptionButton(QAbstractButton):
    """Windows/Linux-Fensterbutton mit weichem Hover."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(QSize(40, 30))
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._hover:
            bg = QColor(232, 17, 35, 220) if self.kind == "close" else QColor(255, 255, 255, 28)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 8, 8)
        draw_glyph(p, self.kind, QRectF(self.width() / 2 - 6, self.height() / 2 - 6, 12, 12), style.TEXT)


class TitleBar(QWidget):
    closeRequested = Signal()
    minimizeRequested = Signal()
    maximizeRequested = Signal()

    HEIGHT = 44

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 12, 0)
        lay.setSpacing(10)

        self.logo = QWidget()
        self.logo.setFixedSize(22, 22)
        self.logo.paintEvent = self._paint_logo  # type: ignore[assignment]
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 700; font-size: 14px; letter-spacing: 0.3px;")
        self.subtitle = QLabel("")
        self.subtitle.setProperty("muted", True)
        self.subtitle.setStyleSheet("font-size: 12px;")

        brand = QHBoxLayout()
        brand.setSpacing(8)
        brand.addWidget(self.title)
        brand.addWidget(self.subtitle)

        if pu.IS_MAC:
            lights = TrafficLights(self)
            lights.close_btn.clicked.connect(self.closeRequested)
            lights.min_btn.clicked.connect(self.minimizeRequested)
            lights.max_btn.clicked.connect(self.maximizeRequested)
            lay.addWidget(lights)
            lay.addStretch(1)
            lay.addLayout(brand)
            lay.addStretch(1)
            spacer = QWidget()
            spacer.setFixedWidth(lights.sizeHint().width())
            lay.addWidget(spacer)
        else:
            lay.addLayout(brand)
            lay.addStretch(1)
            for kind, sig in (("minimize", self.minimizeRequested), ("maximize", self.maximizeRequested),
                              ("close", self.closeRequested)):
                b = CaptionButton(kind, self)
                b.clicked.connect(sig)
                lay.addWidget(b)

    def _paint_logo(self, _):
        p = QPainter(self.logo)
        draw_logo(p, QRectF(0, 0, 22, 22))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            handle = self.window().windowHandle()
            if handle and handle.startSystemMove():
                e.accept()
                return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.maximizeRequested.emit()
