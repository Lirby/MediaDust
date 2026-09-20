"""Queue-Tabelle mit Verlaufs-Fortschrittsbalken, Status-Pills und Aktions-Buttons pro Zeile."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLabel, QStyle, QStyledItemDelegate,
                               QStyleOptionViewItem, QTableView, QVBoxLayout, QWidget)

from queue_manager import ACTIVE, QueueModel
from ui import style
from ui.icons import draw_glyph, draw_logo
from ui.widgets import paint_liquid_glass

ROW_HEIGHT = 46


class ProgressDelegate(QStyledItemDelegate):
    def __init__(self, view: "QueueView"):
        super().__init__(view)
        self.view = view

    def paint(self, p: QPainter, opt: QStyleOptionViewItem, index):
        self.initStyleOption(opt, index)
        opt.text = ""
        self.view.style().drawControl(QStyle.CE_ItemViewItem, opt, p, self.view)
        item = index.data(QueueModel.ItemRole)
        value = max(0.0, min(100.0, float(item.progress)))
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(opt.rect).adjusted(10, 0, -10, 0)
        bar = QRectF(r.left(), r.center().y() - 4, r.width() - 46, 8)
        track = QPainterPath()
        track.addRoundedRect(bar, bar.height() / 2, bar.height() / 2)
        p.fillPath(track, QColor(0, 0, 30, 70))
        p.setPen(Qt.NoPen)
        if value > 0:
            fill = QRectF(bar.left(), bar.top(), max(8.0, bar.width() * value / 100), bar.height())
            g = QLinearGradient(bar.topLeft(), bar.topRight())
            if item.status == "finished":
                g.setColorAt(0, QColor(52, 211, 153))
                g.setColorAt(1, QColor(45, 212, 191))
            elif item.status in ("error", "canceled"):
                g.setColorAt(0, QColor(248, 113, 113, 160))
                g.setColorAt(1, QColor(248, 113, 113, 160))
            elif item.status == "paused":
                g.setColorAt(0, QColor(251, 191, 36, 180))
                g.setColorAt(1, QColor(245, 158, 11, 180))
            else:
                g.setColorAt(0, style.ACCENT_1)
                g.setColorAt(0.6, style.ACCENT_2)
                g.setColorAt(1, style.ACCENT_3)
            path = QPainterPath()
            path.addRoundedRect(fill, fill.height() / 2, fill.height() / 2)
            p.fillPath(path, g)
            if item.status in ACTIVE:
                # wandernder Glanz auf aktiven Balken
                phase = self.view.shimmer_phase
                sx = fill.left() + (fill.width() + 60) * phase - 30
                shine = QLinearGradient(sx - 30, 0, sx + 30, 0)
                shine.setColorAt(0, QColor(255, 255, 255, 0))
                shine.setColorAt(0.5, QColor(255, 255, 255, 110))
                shine.setColorAt(1, QColor(255, 255, 255, 0))
                p.fillPath(path, shine)
        elif item.status == "resolving":
            phase = self.view.shimmer_phase
            seg = QRectF(bar.left() + (bar.width() - 40) * phase, bar.top(), 40, bar.height())
            g = QLinearGradient(seg.topLeft(), seg.topRight())
            g.setColorAt(0, QColor(139, 92, 246, 0))
            g.setColorAt(0.5, QColor(139, 92, 246, 200))
            g.setColorAt(1, QColor(139, 92, 246, 0))
            p.setBrush(g)
            p.drawRoundedRect(seg, 4, 4)
        p.setPen(style.TEXT if value > 0 else style.TEXT_MUTED)
        f = p.font()
        f.setPointSizeF(max(8.0, f.pointSizeF() - 1))
        p.setFont(f)
        p.drawText(QRectF(bar.right() + 6, r.top(), 40, r.height()), Qt.AlignVCenter | Qt.AlignRight,
                   f"{value:.0f} %")
        p.restore()


class StatusDelegate(QStyledItemDelegate):
    def paint(self, p: QPainter, opt: QStyleOptionViewItem, index):
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        opt.widget.style().drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)
        item = index.data(QueueModel.ItemRole)
        color = QColor(style.STATUS_COLORS.get(item.status, style.TEXT_MUTED))
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(opt.rect).adjusted(8, 0, -6, 0)
        fm = opt.fontMetrics
        label = fm.elidedText(text, Qt.ElideRight, int(r.width() - 26))
        pill = QRectF(r.left(), r.center().y() - 11, fm.horizontalAdvance(label) + 26, 22)
        bg = QColor(color)
        bg.setAlpha(38)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(pill, 11, 11)
        p.setBrush(color)
        p.drawEllipse(QRectF(pill.left() + 9, pill.center().y() - 3, 6, 6))
        p.setPen(color.lighter(125))
        p.drawText(pill.adjusted(20, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, label)
        p.restore()


class TitleDelegate(QStyledItemDelegate):
    def paint(self, p: QPainter, opt: QStyleOptionViewItem, index):
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        opt.widget.style().drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)
        item = index.data(QueueModel.ItemRole)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(opt.rect).adjusted(10, 0, -6, 0)
        icon_rect = QRectF(r.left(), r.center().y() - 13, 26, 26)
        g = QLinearGradient(icon_rect.topLeft(), icon_rect.bottomRight())
        a1, a2 = QColor(style.ACCENT_1), QColor(style.ACCENT_2)
        a1.setAlpha(70)
        a2.setAlpha(70)
        g.setColorAt(0, a1)
        g.setColorAt(1, a2)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(icon_rect, 8, 8)
        paint_liquid_glass(p, icon_rect, 9, 4)
        draw_glyph(p, "music" if item.mode == "audio" else "video", icon_rect.adjusted(6, 6, -6, -6), style.TEXT)
        tr = r.adjusted(36, 0, 0, 0)
        if item.priority == 1:
            p.setPen(style.ACCENT_3)
        elif item.priority == -1:
            p.setPen(style.TEXT_MUTED)
        else:
            p.setPen(style.TEXT)
        p.drawText(tr, Qt.AlignVCenter | Qt.AlignLeft,
                   opt.fontMetrics.elidedText(text, Qt.ElideRight, int(tr.width())))
        p.restore()


class ActionsDelegate(QStyledItemDelegate):
    """Pause/Fortsetzen · Abbrechen · Entfernen als klickbare Mini-Buttons."""
    SIZE = 28
    GAP = 4

    def __init__(self, view: "QueueView"):
        super().__init__(view)
        self.view = view

    def buttons_for(self, item) -> List[str]:
        if item.status in ACTIVE or item.status in ("queued",):
            first = "pause"
        elif item.status in ("error", "canceled", "finished"):
            first = "retry"
        elif item.status in ("resolving", "confirm"):
            first = ""
        else:
            first = "play"
        return [b for b in (first, "stop" if item.status not in ("finished", "canceled") else "folder", "trash") if b]

    def rects(self, rect, item):
        names = self.buttons_for(item)
        total = len(names) * self.SIZE + (len(names) - 1) * self.GAP
        x = rect.right() - total - 8
        y = rect.center().y() - self.SIZE / 2
        out = []
        for n in names:
            out.append((n, QRectF(x, y, self.SIZE, self.SIZE)))
            x += self.SIZE + self.GAP
        return out

    def paint(self, p: QPainter, opt: QStyleOptionViewItem, index):
        self.initStyleOption(opt, index)
        opt.widget.style().drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)
        item = index.data(QueueModel.ItemRole)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        hover_pos = self.view.hover_pos
        for name, r in self.rects(opt.rect, item):
            hovered = hover_pos is not None and r.contains(hover_pos)
            if hovered:
                tint = QColor(248, 113, 113, 110) if name in ("trash", "stop") else QColor(139, 82, 246, 130)
                paint_liquid_glass(p, r, r.height() / 2, 12, tint)
            else:
                paint_liquid_glass(p, r, r.height() / 2, 8)
            draw_glyph(p, name, r.adjusted(7, 7, -7, -7), style.TEXT if hovered else QColor(200, 204, 232))
        p.restore()

    def editorEvent(self, event, model, opt, index):
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            item = index.data(QueueModel.ItemRole)
            for name, r in self.rects(opt.rect, item):
                if r.contains(event.position()):
                    self.view.actionClicked.emit(name, item.id)
                    return True
        if event.type() == QEvent.MouseButtonPress:
            item = index.data(QueueModel.ItemRole)
            if any(r.contains(event.position()) for _, r in self.rects(opt.rect, item)):
                return True
        return False

    def helpEvent(self, event, view, opt, index):
        item = index.data(QueueModel.ItemRole)
        tips = {"pause": "Pausieren", "play": "Fortsetzen", "retry": "Erneut versuchen",
                "stop": "Abbrechen", "trash": "Entfernen", "folder": "Im Ordner anzeigen"}
        for name, r in self.rects(opt.rect, item):
            if r.contains(event.pos()):
                from PySide6.QtWidgets import QToolTip
                QToolTip.showText(event.globalPos(), tips.get(name, ""), view)
                return True
        return super().helpEvent(event, view, opt, index)


class EmptyState(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(8)
        logo = QWidget()
        logo.setFixedSize(64, 64)
        logo.paintEvent = lambda _e, w=logo: draw_logo(QPainter(w), QRectF(0, 0, 64, 64))  # type: ignore
        t = QLabel("Noch keine Downloads")
        t.setStyleSheet("font-size: 17px; font-weight: 700;")
        s = QLabel("Link oben einfügen, „Links hinzufügen“ öffnen – oder einfach einen Link kopieren.\n"
                   "MediaDust erkennt ihn automatisch.")
        s.setProperty("muted", True)
        s.setAlignment(Qt.AlignCenter)
        for w in (logo, t, s):
            lay.addWidget(w, 0, Qt.AlignHCenter)


class QueueView(QTableView):
    actionClicked = Signal(str, str)   # Aktion, item_id

    def __init__(self, model: QueueModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.hover_pos = None
        self.shimmer_phase = 0.0
        self.setMouseTracking(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setFrameShape(QTableView.NoFrame)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setFocusPolicy(Qt.StrongFocus)
        self.viewport().setAutoFillBackground(False)
        self.setAttribute(Qt.WA_MacShowFocusRect, False)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(QHeaderView.Fixed)
        vh.setDefaultSectionSize(ROW_HEIGHT)
        hh = self.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setMinimumSectionSize(40)
        widths = {QueueModel.COL_FORMAT: 110, QueueModel.COL_STATUS: 150, QueueModel.COL_PROGRESS: 190,
                  QueueModel.COL_SPEED: 95, QueueModel.COL_ETA: 80, QueueModel.COL_SIZE: 85,
                  QueueModel.COL_ACTIONS: 104}
        hh.setSectionResizeMode(QueueModel.COL_TITLE, QHeaderView.Stretch)
        for col, w in widths.items():
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
            self.setColumnWidth(col, w)
        hh.setSectionResizeMode(QueueModel.COL_ACTIONS, QHeaderView.Fixed)

        self.setItemDelegateForColumn(QueueModel.COL_TITLE, TitleDelegate(self))
        self.setItemDelegateForColumn(QueueModel.COL_STATUS, StatusDelegate(self))
        self.setItemDelegateForColumn(QueueModel.COL_PROGRESS, ProgressDelegate(self))
        self.actions_delegate = ActionsDelegate(self)
        self.setItemDelegateForColumn(QueueModel.COL_ACTIONS, self.actions_delegate)

        self.empty = EmptyState(self.viewport())
        model.rowsInserted.connect(self._update_empty)
        model.rowsRemoved.connect(self._update_empty)
        model.modelReset.connect(self._update_empty)
        self._update_empty()

        self._shimmer = QTimer(self, interval=40, timeout=self._tick)
        self._shimmer.start()

    def _tick(self):
        items = self.model().items
        if not any(i.status in ACTIVE or i.status == "resolving" for i in items):
            return
        self.shimmer_phase = (self.shimmer_phase + 0.018) % 1.0
        top = self.rowAt(0)
        bottom = self.rowAt(self.viewport().height() - 1)
        bottom = len(items) - 1 if bottom < 0 else bottom
        for row in range(max(0, top), bottom + 1):
            if items[row].status in ACTIVE or items[row].status == "resolving":
                self.viewport().update(self.visualRect(self.model().index(row, QueueModel.COL_PROGRESS)))

    def _update_empty(self, *_):
        self.empty.setVisible(self.model().rowCount() == 0)
        self.empty.setGeometry(self.viewport().rect())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.empty.setGeometry(self.viewport().rect())

    def mouseMoveEvent(self, e):
        self.hover_pos = e.position()
        idx = self.indexAt(e.position().toPoint())
        if idx.isValid() and idx.column() == QueueModel.COL_ACTIONS:
            self.viewport().update(self.visualRect(idx))
            item = idx.data(QueueModel.ItemRole)
            over = any(r.contains(e.position()) for _, r in
                       self.actions_delegate.rects(self.visualRect(idx), item))
            self.viewport().setCursor(Qt.PointingHandCursor if over else Qt.ArrowCursor)
        else:
            self.viewport().unsetCursor()
        if getattr(self, "_last_action_idx", None) is not None and self._last_action_idx != idx:
            self.viewport().update(self.visualRect(self._last_action_idx))
        self._last_action_idx = idx
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.hover_pos = None
        self.viewport().update()
        super().leaveEvent(e)

    def selected_ids(self) -> List[str]:
        rows = sorted({i.row() for i in self.selectionModel().selectedRows()})
        items = self.model().items
        return [items[r].id for r in rows if r < len(items)]

    def sizeHint(self):
        return QSize(900, 400)
