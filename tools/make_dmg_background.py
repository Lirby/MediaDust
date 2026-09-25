"""Erzeugt den DMG-Hintergrund (dunkles lila Milchglas + Pfeil) als assets/dmg_background.tiff (1x + 2x).

Aufruf: python tools/make_dmg_background.py
Layout passt zu build_dmg.sh: Fenster 640×400, App bei x=160, Programme bei x=480, y=190.
"""
from __future__ import annotations

import random
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "dmg_background.tiff"
W, H = 640, 400


def render(scale: int) -> QImage:
    img = QImage(W * scale, H * scale, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(scale, scale)

    # Grundverlauf: dunkles Lila
    base = QLinearGradient(0, 0, W, H)
    base.setColorAt(0, QColor("#241040"))
    base.setColorAt(1, QColor("#170a2b"))
    p.fillRect(QRectF(0, 0, W, H), base)

    # Weiche Farbflecken hinter dem Glas
    for x, y, r, color in [(90, 70, 260, "#5b2a9e"), (560, 330, 280, "#4a2191"),
                           (520, 40, 200, "#6d34b8"), (130, 380, 220, "#3b1a78")]:
        g = QRadialGradient(QPointF(x, y), r)
        c = QColor(color)
        g.setColorAt(0, c)
        c.setAlpha(0)
        g.setColorAt(1, c)
        p.fillRect(QRectF(0, 0, W, H), g)

    # Feines Rauschen (Milchglas-Körnung)
    rnd = random.Random(7)
    p.setPen(Qt.NoPen)
    for _ in range(W * H // 6):
        v = rnd.randint(0, 255)
        p.setBrush(QColor(v, v, v, 9))
        p.drawRect(QRectF(rnd.uniform(0, W), rnd.uniform(0, H), 0.6, 0.6))

    # Dunkle Glasscheibe mit hellem Rand
    pane = QRectF(40, 50, W - 80, H - 100)
    tint = QLinearGradient(pane.topLeft(), pane.bottomLeft())
    tint.setColorAt(0, QColor(150, 110, 220, 70))
    tint.setColorAt(1, QColor(90, 50, 160, 45))
    p.setBrush(tint)
    p.setPen(QPen(QColor(200, 170, 255, 110), 1.2))
    p.drawRoundedRect(pane, 24, 24)

    # Helle Glasstreifen hinter den Symbolnamen – Finder schreibt sie immer schwarz
    for cx in (160, 480):
        plate = QRectF(cx - 66, 250, 132, 26)
        p.setBrush(QColor(225, 208, 255, 215))
        p.setPen(QPen(QColor(255, 255, 255, 150), 1))
        p.drawRoundedRect(plate, 13, 13)

    # Pfeil von der App zum Programme-Ordner
    y = 180
    pen = QPen(QColor(200, 165, 255, 230), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    shaft = QPainterPath(QPointF(262, y))
    shaft.cubicTo(QPointF(300, y - 16), QPointF(340, y - 16), QPointF(376, y))
    p.drawPath(shaft)
    head = QPainterPath(QPointF(362, y - 13))
    head.lineTo(QPointF(378, y + 1))
    head.lineTo(QPointF(359, y + 9))
    p.drawPath(head)

    p.end()
    return img


def main() -> None:
    app = QGuiApplication(sys.argv)  # noqa: F841
    with tempfile.TemporaryDirectory() as tmp:
        one, two = Path(tmp) / "bg.png", Path(tmp) / "bg@2x.png"
        for scale, path in ((1, one), (2, two)):
            img = render(scale)
            dpm = round(72 * scale / 0.0254)  # 72 bzw. 144 dpi → beide 640×400 pt
            img.setDotsPerMeterX(dpm)
            img.setDotsPerMeterY(dpm)
            img.save(str(path))
        subprocess.run(["tiffutil", "-cathidpicheck", str(one), str(two), "-out", str(OUT)], check=True)
    print(f"✓ {OUT}")


if __name__ == "__main__":
    main()
