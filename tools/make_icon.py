"""Erzeugt ein Vektor-Platzhalter-Icon (assets/icon.png, icon.icns, icon.ico).

ACHTUNG: überschreibt ein eigenes Icon in assets/ – für eigene Bilder tools/png_to_icns.py nutzen.

Aufruf: python tools/make_icon.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath  # noqa: E402

from ui.icons import _draw_vector_logo as draw_logo, _soft_glow  # noqa: E402

ASSETS = ROOT / "assets"


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    # macOS-Raster: Motiv nimmt ca. 80 % der Fläche ein
    inset = size * 0.1
    rect = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
    if size >= 64:  # weicher Schatten unter der Glasfläche
        shadow = QPainterPath()
        shadow.addRoundedRect(rect.translated(0, size * 0.015), rect.width() * 0.24, rect.width() * 0.24)
        p.setOpacity(0.55)
        p.drawImage(0, 0, _soft_glow(shadow, QSize(size, size), QColor(20, 10, 60, 200), size * 0.03))
        p.setOpacity(1.0)
    draw_logo(p, rect)
    p.end()
    return img


def main() -> None:
    QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
    ASSETS.mkdir(exist_ok=True)
    render(1024).save(str(ASSETS / "icon.png"))
    render(256).save(str(ASSETS / "icon.ico"))

    if shutil.which("iconutil"):
        with tempfile.TemporaryDirectory() as tmp:
            iconset = Path(tmp) / "icon.iconset"
            iconset.mkdir()
            for base in (16, 32, 128, 256, 512):
                render(base).save(str(iconset / f"icon_{base}x{base}.png"))
                render(base * 2).save(str(iconset / f"icon_{base}x{base}@2x.png"))
            subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "icon.icns")], check=True)
    else:
        print("iconutil nicht gefunden (nur macOS) – icon.icns übersprungen")
    print("Icons erzeugt in", ASSETS)


if __name__ == "__main__":
    main()
