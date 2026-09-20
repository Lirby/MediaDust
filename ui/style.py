"""Farben und QSS-Stylesheet: Glassmorphism/Aero in Dunkelblau und Lila."""
from __future__ import annotations

import sys

from PySide6.QtGui import QColor

# Palette
BG_TOP = QColor(12, 6, 30)          # fast schwarzes Lila
BG_MID = QColor(20, 8, 44)          # sehr dunkles Lila
BG_BOTTOM = QColor(28, 8, 56)       # dunkles Violett
ACCENT_1 = QColor(64, 110, 255)     # Blau
ACCENT_2 = QColor(139, 82, 246)     # Violett
ACCENT_3 = QColor(196, 150, 255)    # Lila-Glanz
TEXT = QColor(236, 238, 255)
TEXT_MUTED = QColor(150, 162, 210)
GLASS = QColor(255, 255, 255, 16)
GLASS_BORDER = QColor(255, 255, 255, 34)
SUCCESS = QColor(52, 211, 153)
WARNING = QColor(251, 191, 36)
DANGER = QColor(248, 113, 113)

STATUS_COLORS = {
    "downloading": ACCENT_1, "processing": ACCENT_3, "queued": TEXT_MUTED, "resolving": TEXT_MUTED,
    "confirm": WARNING, "paused": WARNING, "finished": SUCCESS, "error": DANGER, "canceled": TEXT_MUTED,
}

# macOS: Systemschrift (SF) über Qt-Standard; sonst eine moderne Schrift-Kette
FONT_RULE = "" if sys.platform == "darwin" else \
    'font-family: "Segoe UI Variable", "Segoe UI", "Inter", "Ubuntu", "Cantarell", sans-serif;'

QSS = f"""
* {{
    {FONT_RULE}
    font-size: 13px;
    color: rgb(234, 236, 250);
    outline: none;
}}
QWidget#Root, QWidget#Central {{ background: transparent; }}
QToolTip {{
    background-color: rgb(26, 12, 54);
    color: rgb(234, 236, 250);
    border: none;
    border-radius: 8px;
    padding: 6px 8px;
}}
QLabel {{ background: transparent; }}
QLabel#Muted, QLabel[muted="true"] {{ color: rgb(150, 162, 210); }}
QLabel#SectionTitle {{ font-size: 12px; font-weight: 600; color: rgb(190, 170, 255); letter-spacing: 0.5px; }}
QLabel#DialogTitle {{ font-size: 17px; font-weight: 700; }}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
    background-color: rgba(255, 255, 255, 13);
    border: none;
    border-radius: 16px;
    padding: 7px 14px;
    selection-background-color: rgba(139, 92, 246, 150);
}}
QLineEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QComboBox:hover {{
    background-color: rgba(255, 255, 255, 19);
}}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    background-color: rgba(190, 160, 255, 30);
    border: none;
}}
QLineEdit#QuickAdd {{ border-radius: 20px; padding: 9px 18px; font-size: 14px; min-height: 20px; }}
QPlainTextEdit {{ border-radius: 18px; padding: 10px 14px; font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace; font-size: 12px; }}

QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url(@ASSETS@/chevron-down.png); width: 10px; height: 10px; margin-right: 8px; }}
QComboBox QAbstractItemView {{
    background-color: rgba(26, 12, 54, 250);
    border: none;
    border-radius: 12px;
    padding: 5px;
    outline: 0;
    selection-background-color: rgba(150, 105, 235, 120);
}}
QComboBox QAbstractItemView::item {{
    min-height: 26px;
    padding: 2px 10px;
    border: none;
    border-radius: 8px;
    color: rgb(236, 238, 255);
}}
QComboBox QAbstractItemView::item:hover {{ background-color: rgba(255, 255, 255, 18); }}
QComboBox QAbstractItemView::item:selected {{ background-color: rgba(150, 105, 235, 120); }}
QComboBox {{ combobox-popup: 0; }}
QSpinBox {{ padding-right: 22px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 20px; border: none; background: transparent;
    subcontrol-origin: border; margin-right: 4px; }}
QSpinBox::up-button {{ subcontrol-position: top right; margin-top: 3px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; margin-bottom: 3px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: rgba(255, 255, 255, 25); border-radius: 5px; }}
QSpinBox::up-arrow {{ image: url(@ASSETS@/chevron-up.png); width: 9px; height: 9px; }}
QSpinBox::down-arrow {{ image: url(@ASSETS@/chevron-down.png); width: 9px; height: 9px; }}

QCheckBox {{ spacing: 9px; background: transparent; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border-radius: 9px;
    border: none;
    background-color: rgba(255, 255, 255, 30);
}}
QCheckBox::indicator:hover {{ background-color: rgba(255, 255, 255, 45); }}
QCheckBox::indicator:checked {{
    border: none;
    background-color: rgba(150, 105, 235, 170);
    image: url(@ASSETS@/check.png);
}}

QTableView {{
    background: transparent;
    border: none;
    gridline-color: transparent;
    selection-background-color: rgba(255, 255, 255, 16);
    selection-color: rgb(255, 255, 255);
    alternate-background-color: transparent;
}}
QTableView::item {{ padding: 0 8px; border: none; border-bottom: 1px solid rgba(255, 255, 255, 5); }}
QTableView::item:hover {{ background-color: rgba(255, 255, 255, 10); }}
QTableView::item:selected {{ background-color: rgba(255, 255, 255, 16); }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{
    background: transparent;
    color: rgb(150, 162, 210);
    font-size: 11px; font-weight: 600;
    text-transform: uppercase;
    border: none;
    border: none;
    padding: 10px 8px;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

QTreeView {{
    background: rgba(255, 255, 255, 8);
    border: none;
    border-radius: 16px;
    padding: 6px;
    selection-background-color: rgba(255, 255, 255, 16);
    show-decoration-selected: 0;
}}
QTreeView::item {{ padding: 5px 4px; border-radius: 8px; }}
QTreeView::item:hover {{ background: rgba(255, 255, 255, 10); }}
QTreeView::item:selected {{ background: rgba(255, 255, 255, 16); color: rgb(236, 238, 255); }}
QTreeView::branch {{ background: transparent; }}
QTreeView::branch:has-children:closed {{ image: url(@ASSETS@/chevron-right.png); }}
QTreeView::branch:has-children:open {{ image: url(@ASSETS@/chevron-down.png); }}
QTreeView::indicator {{ width: 16px; height: 16px; border-radius: 8px; background-color: rgba(255, 255, 255, 30); }}
QTreeView::indicator:checked {{ background-color: rgba(150, 105, 235, 190); image: url(@ASSETS@/check.png); }}
QTreeView::indicator:indeterminate {{ background-color: rgba(150, 105, 235, 110); image: url(@ASSETS@/dash.png); }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 45); border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(160, 140, 255, 140); }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: rgba(255, 255, 255, 45); border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QMenu {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(26, 12, 54, 248), stop:1 rgba(32, 10, 64, 248));
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 14px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: 9px; background: transparent; }}
QMenu::item:selected {{ background-color: rgba(210, 185, 255, 70); }}
QMenu::item:disabled {{ color: rgb(110, 114, 150); }}
QMenu::separator {{ height: 1px; background: rgba(255, 255, 255, 30); margin: 5px 8px; }}
QMenu::icon {{ padding-left: 8px; }}

QProgressBar {{
    background-color: rgba(255, 255, 255, 18);
    border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgb(64,110,255), stop:0.6 rgb(139,82,246), stop:1 rgb(196,150,255));
}}
"""


def _render_assets(folder) -> None:
    """Rendert kleine Pfeil-/Häkchen-Grafiken für das Stylesheet (1x und @2x)."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QImage, QPainter, QPen

    def draw(name, size, points, color, width):
        for scale, suffix in ((1, ""), (2, "@2x")):
            img = QImage(size * scale, size * scale, QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            pen = QPen(color, width * scale)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.drawPolyline([QPointF(x * size * scale, y * size * scale) for x, y in points])
            p.end()
            img.save(str(folder / f"{name}{suffix}.png"))

    muted = QColor(190, 195, 230)
    draw("chevron-down", 10, [(0.15, 0.35), (0.5, 0.7), (0.85, 0.35)], muted, 1.6)
    draw("chevron-up", 10, [(0.15, 0.65), (0.5, 0.3), (0.85, 0.65)], muted, 1.6)
    draw("chevron-right", 10, [(0.35, 0.15), (0.7, 0.5), (0.35, 0.85)], muted, 1.6)
    draw("dash", 18, [(0.3, 0.5), (0.7, 0.5)], QColor(255, 255, 255), 2.0)
    draw("check", 18, [(0.26, 0.52), (0.43, 0.68), (0.75, 0.33)], QColor(255, 255, 255), 2.0)


def stylesheet() -> str:
    from platform_utils import data_dir
    folder = data_dir() / "cache" / "qss"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        _render_assets(folder)
    except Exception as exc:  # Stylesheet funktioniert auch ohne Grafiken
        print(f"[MediaDust] QSS-Grafiken nicht erzeugt: {exc}")
    return QSS.replace("@ASSETS@", folder.as_posix())
