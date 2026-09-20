"""Baut assets/icon.icns (und icon.ico) aus assets/icon.png – für ein selbst gestaltetes Icon.

Aufruf: python tools/png_to_icns.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402

ASSETS = ROOT / "assets"


def square(img: QImage) -> QImage:
    """Auf ein Quadrat bringen (zentriert, transparent aufgefüllt)."""
    side = max(img.width(), img.height())
    out = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawImage((side - img.width()) // 2, (side - img.height()) // 2, img)
    p.end()
    return out


def main() -> None:
    QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
    src = square(QImage(str(ASSETS / "icon.png")).convertToFormat(QImage.Format_ARGB32_Premultiplied))

    def sized(n: int) -> QImage:
        return src.scaled(n, n, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            sized(base).save(str(iconset / f"icon_{base}x{base}.png"))
            sized(base * 2).save(str(iconset / f"icon_{base}x{base}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "icon.icns")], check=True)
    sized(256).save(str(ASSETS / "icon.ico"))
    print("icon.icns / icon.ico aus icon.png erzeugt")


if __name__ == "__main__":
    main()
