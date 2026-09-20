"""Dialoge im Glass-Stil: Links hinzufügen (Massen-Import), Einstellungen, Playlist-Bestätigung."""
from __future__ import annotations

import re
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListView, QPlainTextEdit, QSpinBox, QStackedWidget, QStyledItemDelegate, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

import platform_utils as pu
import series
from settings import (AFTER_COMPLETE, AUDIO_BITRATES, AUDIO_FORMATS, LOSSLESS_AUDIO, VIDEO_FORMATS,
                      VIDEO_QUALITIES)
from ui.widgets import GlassButton, GlassDialog, GlassPanel, SegmentedToggle, message

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def extract_urls(text: str) -> List[str]:
    seen, out = set(), []
    for m in URL_RE.finditer(text):
        url = m.group(0).rstrip(").,;]>")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _combo(options, current, min_width: int = 64) -> QComboBox:
    cb = QComboBox()
    for key, label in options:
        cb.addItem(label, key)
    idx = cb.findData(current)
    cb.setCurrentIndex(max(0, idx))
    polish_combo(cb, min_width)
    return cb


_POPUP_QSS = """
QListView {
    background-color: rgba(26, 12, 54, 250);
    border: none;
    border-radius: 12px;
    padding: 5px;
    outline: 0;
}
QListView::item {
    padding: 0px 10px;
    border: none;
    border-radius: 8px;
    color: rgb(236, 238, 255);
}
QListView::item:hover { background-color: rgba(255, 255, 255, 20); }
QListView::item:selected { background-color: rgba(150, 105, 235, 130); }
"""


class _PopupDelegate(QStyledItemDelegate):
    """Feste, luftige Zeilenhöhe für Auswahllisten."""
    ROW = 30

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(self.ROW)
        return size


def polish_combo(cb: QComboBox, min_width: int = 64) -> None:
    """Liste als abgerundetes Glas-Popup (ohne schwarzen Rahmen) und Breite passend zum gewählten Text."""
    view = QListView()
    view.setStyleSheet(_POPUP_QSS)                     # vor dem Einhängen, sonst falsches Zeilenlayout
    view.setItemDelegate(_PopupDelegate(view))         # damit die QSS-Regeln für Einträge greifen
    cb.setView(view)
    cb.setItemDelegate(view.itemDelegate())
    view.doItemsLayout()
    popup = view.window()
    popup.setWindowFlags(popup.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    popup.setAttribute(Qt.WA_TranslucentBackground)
    popup.setStyleSheet("QComboBoxPrivateContainer { background: transparent; border: none; }")

    def fit(*_):
        fm = cb.fontMetrics()
        cb.setFixedWidth(max(min_width, fm.horizontalAdvance(cb.currentText()) + 58))
        widest = max((fm.horizontalAdvance(cb.itemText(i)) for i in range(cb.count())), default=0)
        view.setMinimumWidth(widest + 44)
        view.doItemsLayout()

    cb.currentIndexChanged.connect(fit)
    fit()


class FormatPicker(QWidget):
    """Video/Audio-Umschalter + Dateiformat + Auflösung bzw. Bitrate."""
    changed = Signal()

    def __init__(self, mode: str, quality: str, bitrate: str, video_fmt: str = "mp4",
                 audio_fmt: str = "mp3", parent=None, compact: bool = False):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.toggle = SegmentedToggle([("video", "Video"), ("audio", "Audio")], icons=["video", "music"])
        self.toggle.setFixedWidth(180)
        self.toggle.setValue(mode)
        self.video_fmt = _combo(VIDEO_FORMATS, video_fmt)
        self.audio_fmt = _combo(AUDIO_FORMATS, audio_fmt)
        self.quality = _combo(VIDEO_QUALITIES, quality)
        self.bitrate = _combo(AUDIO_BITRATES, bitrate)
        for cb in (self.video_fmt, self.audio_fmt, self.quality, self.bitrate):
            cb.setToolTip("Dateiformat" if cb in (self.video_fmt, self.audio_fmt) else
                          ("Auflösung (höchstens)" if cb is self.quality else "Bitrate"))
            cb.currentIndexChanged.connect(self._sync)
        for w in (self.toggle, self.video_fmt, self.audio_fmt, self.quality, self.bitrate):
            lay.addWidget(w)
        if compact:
            for cb in (self.video_fmt, self.audio_fmt, self.quality, self.bitrate):
                cb.setFixedHeight(40)
            self.toggle.setFixedHeight(40)
        else:
            lay.addStretch(1)
        self.toggle.changed.connect(self._sync)
        self._sync()

    def _sync(self, *_):
        video = self.toggle.value() == "video"
        self.video_fmt.setVisible(video)
        self.quality.setVisible(video)
        self.audio_fmt.setVisible(not video)
        self.bitrate.setVisible(not video and self.audio_fmt.currentData() not in LOSSLESS_AUDIO)
        self.changed.emit()

    def set_mode(self, mode: str) -> None:
        self.toggle.setValue(mode, animate=True)
        self._sync()

    def values(self):
        """(Modus, Dateiformat, Auflösung, Bitrate)"""
        mode = self.toggle.value()
        fmt = (self.video_fmt if mode == "video" else self.audio_fmt).currentData()
        return mode, fmt, self.quality.currentData(), self.bitrate.currentData()


class FolderPicker(QWidget):
    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.edit = QLineEdit(path)
        btn = GlassButton("Wählen …", icon_name="folder", compact=True)
        btn.setFixedHeight(34)
        btn.clicked.connect(self._pick)
        lay.addWidget(self.edit, 1)
        lay.addWidget(btn)

    def _pick(self):
        path = QFileDialog.getExistingDirectory(self, "Zielordner wählen", self.edit.text())
        if path:
            self.edit.setText(path)

    def value(self) -> str:
        return self.edit.text().strip()


class AddLinksDialog(GlassDialog):
    def __init__(self, settings, initial_text: str = "", parent=None):
        super().__init__("Links hinzufügen", parent, width=640)
        hint = QLabel("Ein Link pro Zeile – beliebiger Text geht auch, Links werden automatisch herausgefiltert.")
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        self.body.addWidget(hint)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("https://www.youtube.com/watch?v=…\nhttps://vimeo.com/…\nhttps://soundcloud.com/…")
        self.text.setPlainText(initial_text)
        self.text.setMinimumHeight(180)
        self.body.addWidget(self.text)
        self.count = QLabel()
        self.count.setProperty("muted", True)
        self.body.addWidget(self.count)

        panel = GlassPanel()
        form = QFormLayout(panel)
        form.setContentsMargins(16, 14, 16, 14)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.format = FormatPicker(settings.default_mode, settings.default_quality, settings.default_audio_bitrate,
                                   settings.default_video_format, settings.default_audio_format)
        self.folder = FolderPicker(settings.download_dir)
        self.start_now = QCheckBox("Downloads sofort starten")
        self.start_now.setChecked(True)
        form.addRow("Format", self.format)
        form.addRow("Zielordner", self.folder)
        form.addRow("", self.start_now)
        self.body.addWidget(panel)

        self.add_button("Abbrechen", "ghost", role="reject")
        self.ok = self.add_button("Hinzufügen", "primary", role="accept", icon_name="plus")
        self.text.textChanged.connect(self._update_count)
        self._update_count()

    def _update_count(self):
        n = len(self.urls())
        self.count.setText(f"{n} Link{'s' if n != 1 else ''} erkannt")
        self.ok.setEnabled(n > 0)

    def urls(self) -> List[str]:
        return extract_urls(self.text.toPlainText())


class SettingsDialog(GlassDialog):
    """Einstellungen mit den Reitern „Allgemein“ und „Updates“.

    updates: Objekt mit app_version, ytdlp_version, ffmpeg_dir, ffmpeg_is_system,
             downloads_active() und update_libraries(ffmpeg: bool) -> BinaryManager | None.
    """

    def __init__(self, settings, parent=None, updates=None):
        super().__init__("Einstellungen", parent, width=640)
        self.settings = settings
        self.updates = updates

        tabs = SegmentedToggle([("general", "Allgemein"), ("updates", "Updates")], icons=["gear", "retry"])
        tabs.setFixedWidth(280)
        tab_row = QHBoxLayout()
        tab_row.addStretch(1)
        tab_row.addWidget(tabs)
        tab_row.addStretch(1)
        self.body.addLayout(tab_row)
        self.stack = QStackedWidget()
        self.body.addWidget(self.stack, 1)
        self.stack.addWidget(self._general_page(settings))
        self.stack.addWidget(self._updates_page(settings))
        tabs.changed.connect(lambda key: self.stack.setCurrentIndex(0 if key == "general" else 1))

        self.add_button("Abbrechen", "ghost", role="reject")
        self.add_button("Speichern", "primary", role="accept")

    @staticmethod
    def _section(layout: QVBoxLayout, title: str) -> QFormLayout:
        lbl = QLabel(title.upper())
        lbl.setObjectName("SectionTitle")
        layout.addWidget(lbl)
        panel = GlassPanel()
        form = QFormLayout(panel)
        form.setContentsMargins(16, 12, 16, 12)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        layout.addWidget(panel)
        return form

    @staticmethod
    def _spin(value: int, lo: int, hi: int, suffix: str = "") -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setValue(value)
        sp.setSuffix(suffix)
        sp.setFixedWidth(96)
        return sp

    def _general_page(self, settings) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        f = self._section(lay, "Downloads")
        self.folder = FolderPicker(settings.download_dir)
        f.addRow("Zielordner", self.folder)
        self.parallel_video = self._spin(settings.max_parallel_video, 1, 10)
        self.parallel_audio = self._spin(settings.max_parallel_audio, 1, 10)
        par = QHBoxLayout()
        par.setSpacing(10)
        for label, sp in (("Video", self.parallel_video), ("Musik", self.parallel_audio)):
            l = QLabel(label)
            l.setProperty("muted", True)
            par.addWidget(l)
            par.addWidget(sp)
            par.addSpacing(8)
        par.addStretch(1)
        f.addRow("Parallele Downloads", par)
        self.format = FormatPicker(settings.default_mode, settings.default_quality, settings.default_audio_bitrate,
                                   settings.default_video_format, settings.default_audio_format)
        f.addRow("Standardformat", self.format)
        self.threshold = self._spin(settings.playlist_confirm_threshold, 1, 5000)
        f.addRow("Playlist-Nachfrage ab", self.threshold)
        self.autostart_dl = QCheckBox("Neue Downloads automatisch starten")
        self.autostart_dl.setChecked(settings.autostart_downloads)
        f.addRow("", self.autostart_dl)
        self.after = _combo(AFTER_COMPLETE, settings.after_complete)
        f.addRow("Wenn alles fertig ist", self.after)

        g = self._section(lay, "Verhalten")
        self.autostart = QCheckBox("Beim Anmelden automatisch starten")
        self.autostart.setChecked(settings.autostart)
        for w in (self.autostart,):
            g.addRow(w)
        lay.addStretch(1)
        return page

    def _updates_page(self, settings) -> QWidget:
        u = self.updates
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # --- MediaDust selbst (Funktion folgt später)
        f = self._section(lay, "MediaDust")
        ver = QLabel(f"Version {u.app_version if u else '–'}")
        self.app_update_btn = GlassButton("Nach Updates suchen", icon_name="retry", compact=True)
        self.app_update_btn.clicked.connect(self._check_app_update)
        row = QHBoxLayout()
        row.addWidget(ver)
        row.addStretch(1)
        row.addWidget(self.app_update_btn)
        f.addRow(row)
        self.app_update_status = QLabel("")
        self.app_update_status.setProperty("muted", True)
        f.addRow(self.app_update_status)

        # --- Bibliotheken (yt-dlp, ffmpeg)
        g = self._section(lay, "Bibliotheken")
        self.ytdlp_label = QLabel(f"yt-dlp  {u.ytdlp_version if u and u.ytdlp_version else '–'}")
        self.ytdlp_btn = GlassButton("Jetzt aktualisieren", icon_name="download", compact=True)
        self.ytdlp_btn.clicked.connect(lambda: self._update_libs(ffmpeg=False))
        row = QHBoxLayout()
        row.addWidget(self.ytdlp_label)
        row.addStretch(1)
        row.addWidget(self.ytdlp_btn)
        g.addRow(row)

        ff_text = "nicht verfügbar"
        if u and u.ffmpeg_dir:
            ff_text = "über Homebrew/System" if u.ffmpeg_is_system else "eigene Kopie"
        self.ffmpeg_label = QLabel(f"ffmpeg  ({ff_text})")
        self.ffmpeg_btn = GlassButton("Neu herunterladen", icon_name="download", compact=True)
        self.ffmpeg_btn.clicked.connect(lambda: self._update_libs(ffmpeg=True))
        if u and u.ffmpeg_is_system:
            self.ffmpeg_btn.setEnabled(False)
            self.ffmpeg_btn.setToolTip("Wird vom System verwaltet – z. B. mit „brew upgrade ffmpeg“ aktualisieren")
        row = QHBoxLayout()
        row.addWidget(self.ffmpeg_label)
        row.addStretch(1)
        row.addWidget(self.ffmpeg_btn)
        g.addRow(row)

        self.lib_status = QLabel("")
        self.lib_status.setProperty("muted", True)
        self.lib_status.setWordWrap(True)
        g.addRow(self.lib_status)
        self.auto_update_cb = QCheckBox("yt-dlp bei jedem Start automatisch aktualisieren")
        self.auto_update_cb.setChecked(settings.auto_update)
        g.addRow(self.auto_update_cb)
        self.ffmpeg_auto_cb = QCheckBox("ffmpeg automatisch aktualisieren (einmal pro Woche)")
        self.ffmpeg_auto_cb.setChecked(settings.ffmpeg_auto_update)
        if u and u.ffmpeg_is_system:
            self.ffmpeg_auto_cb.setEnabled(False)
            self.ffmpeg_auto_cb.setToolTip("ffmpeg wird vom System (z. B. Homebrew) verwaltet")
        g.addRow(self.ffmpeg_auto_cb)
        if settings.ffmpeg_last_check:
            import datetime
            when = datetime.datetime.fromtimestamp(settings.ffmpeg_last_check).strftime("%d.%m.%Y %H:%M")
            last = QLabel(f"ffmpeg zuletzt geprüft: {when}")
            last.setProperty("muted", True)
            last.setStyleSheet("font-size: 11px;")
            g.addRow(last)

        info = QLabel(f"Daten: {pu.data_dir()}")
        info.setProperty("muted", True)
        info.setStyleSheet("font-size: 11px;")
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addStretch(1)
        return page

    def _check_app_update(self):
        # TODO: Update-Prüfung für MediaDust selbst – wird später angebunden
        self.app_update_status.setText("Die Update-Suche für MediaDust folgt in einer späteren Version.")

    def _update_libs(self, ffmpeg: bool):
        u = self.updates
        if u is None:
            return
        if u.downloads_active():
            self.lib_status.setText("Bitte zuerst laufende Downloads pausieren – dann aktualisieren.")
            return
        bm = u.update_libraries(ffmpeg=ffmpeg)
        if bm is None:
            self.lib_status.setText("Es läuft bereits eine Aktualisierung …")
            return
        for b in (self.ytdlp_btn, self.ffmpeg_btn):
            b.setEnabled(False)
        bm.status.connect(self.lib_status.setText)
        bm.ytdlp_version.connect(lambda v: self.ytdlp_label.setText(f"yt-dlp  {v}"))
        bm.ready.connect(lambda *_: self._lib_done("Fertig – alles aktuell."))
        bm.failed.connect(lambda msg, _gk: self._lib_done("Fehler: " + msg.split("\n")[0]))
        bm.warning.connect(lambda msg: self.lib_status.setText(msg.split("\n")[0]))

    def _lib_done(self, text: str):
        self.lib_status.setText(text)
        self.ytdlp_btn.setEnabled(True)
        self.ffmpeg_btn.setEnabled(not (self.updates and self.updates.ffmpeg_is_system))

    def apply(self) -> dict:
        """Überträgt die Werte in settings; gibt geänderte Schlüssel zurück."""
        s = self.settings
        mode, _fmt, quality, bitrate = self.format.values()
        new = {
            "download_dir": self.folder.value() or s.download_dir,
            "default_video_format": self.format.video_fmt.currentData(),
            "default_audio_format": self.format.audio_fmt.currentData(),
            "max_parallel_video": self.parallel_video.value(),
            "max_parallel_audio": self.parallel_audio.value(),
            "default_mode": mode, "default_quality": quality, "default_audio_bitrate": bitrate,
            "playlist_confirm_threshold": self.threshold.value(),
            "autostart_downloads": self.autostart_dl.isChecked(),
            "after_complete": self.after.currentData(),
            "autostart": self.autostart.isChecked(),
            "auto_update": self.auto_update_cb.isChecked(),
            "ffmpeg_auto_update": self.ffmpeg_auto_cb.isChecked(),
        }
        changed = {k: v for k, v in new.items() if getattr(s, k) != v}
        for k, v in new.items():
            setattr(s, k, v)
        s.save()
        return changed


class FormatDialog(GlassDialog):
    """Format/Auflösung für ausgewählte Einträge ändern."""

    def __init__(self, item, count: int, parent=None):
        super().__init__("Format ändern", parent, width=640)
        info = QLabel(f"Gilt für {count} ausgewählte Einträge. Fertige Downloads werden im neuen Format erneut geladen."
                      if count > 1 else "Fertige Downloads werden im neuen Format erneut geladen.")
        info.setProperty("muted", True)
        info.setWordWrap(True)
        self.body.addWidget(info)
        vf = item.container if item.mode == "video" and item.container else "mp4"
        af = item.container if item.mode == "audio" and item.container else "mp3"
        self.format = FormatPicker(item.mode, item.quality, item.audio_bitrate, vf, af)
        self.body.addWidget(self.format)
        self.add_button("Abbrechen", "ghost", role="reject")
        self.add_button("Übernehmen", "primary", role="accept")


def _fmt_duration(sec) -> str:
    if not sec:
        return ""
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class SeriesDialog(GlassDialog):
    """Auswahl von Staffeln/Folgen einer Serie bzw. Einträgen einer großen Playlist."""

    def __init__(self, info: dict, single_possible: bool, parent=None):
        super().__init__("Serie / Playlist hinzufügen", parent, width=720)
        self.info = info
        self.choice = "cancel"
        entries = info["entries"]
        self.is_series = sum(1 for e in entries if e.get("episode") is not None) >= 2

        head = QHBoxLayout()
        head.setSpacing(10)
        name_lbl = QLabel("Name")
        name_lbl.setProperty("muted", True)
        self.name = QLineEdit(info.get("series") or info["title"])
        self.name.setToolTip("Ordnername und Präfix der Dateinamen")
        head.addWidget(name_lbl)
        head.addWidget(self.name, 1)
        self.body.addLayout(head)

        opts = QHBoxLayout()
        opts.setSpacing(18)
        self.series_mode = QCheckBox("Als Serie ordnen (Staffel-Ordner, „S01E03“ im Namen)")
        self.series_mode.setChecked(self.is_series)
        self.show_variants = QCheckBox("Barrierefreie Fassungen / OV")
        self.show_extras = QCheckBox("Extras && Trailer")
        has_variants = any(e.get("variant") for e in entries)
        has_extras = any(e.get("extra") for e in entries)
        self.show_variants.setVisible(has_variants)
        self.show_extras.setVisible(has_extras)
        opts.addWidget(self.series_mode)
        opts.addStretch(1)
        opts.addWidget(self.show_variants)
        opts.addWidget(self.show_extras)
        self.body.addLayout(opts)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)
        self.tree.setUniformRowHeights(True)
        self.tree.setMinimumHeight(360)
        self.tree.setRootIsDecorated(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._items = []   # (QTreeWidgetItem, index)
        self.body.addWidget(self.tree, 1)

        sel = QHBoxLayout()
        b_all = GlassButton("Alle", compact=True)
        b_none = GlassButton("Keine", compact=True)
        b_all.clicked.connect(lambda: self._set_all(True))
        b_none.clicked.connect(lambda: self._set_all(False))
        self.count = QLabel()
        self.count.setProperty("muted", True)
        sel.addWidget(b_all)
        sel.addWidget(b_none)
        sel.addStretch(1)
        sel.addWidget(self.count)
        self.body.addLayout(sel)

        cancel = self.add_button("Abbrechen", "ghost", role="reject")
        cancel.clicked.connect(lambda: setattr(self, "choice", "cancel"))
        if single_possible:
            single = self.add_button("Nur dieses Video")
            single.clicked.connect(self._single)
        self.ok = self.add_button("Hinzufügen", "primary", icon_name="plus")
        self.ok.clicked.connect(self._accept_all)

        self.tree.itemChanged.connect(self._update_count)
        self.show_variants.toggled.connect(self._apply_filters)
        self.show_extras.toggled.connect(self._apply_filters)
        self._apply_filters()

    def _visible(self, e: dict) -> bool:
        return not ((e.get("variant") and not self.show_variants.isChecked()) or
                    (e.get("extra") and not self.show_extras.isChecked()))

    def _build_tree(self):
        entries = self.info["entries"]
        previous = {j: node.checkState(0) == Qt.Checked for node, j in self._items}
        self.tree.blockSignals(True)
        self.tree.clear()
        self._items = []
        groups, order = {}, []
        for i, e in enumerate(entries):
            if not self._visible(e):
                continue
            if e.get("nested"):
                key = ("0", "Unter-Playlists")
            elif e.get("extra"):
                key = ("z", "Extras & Trailer")
            elif e.get("season") is not None:
                key = (f"s{e['season']:06d}", series.season_folder(e["season"]))
            else:
                key = ("y", "Weitere Folgen" if self.is_series else "Einträge")
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(i)
        flat = len(order) == 1
        for key in sorted(order):
            idxs = sorted(groups[key], key=lambda j: (entries[j].get("episode") is None,
                                                       entries[j].get("episode") or 0, j))
            parent = None
            if not flat:
                parent = QTreeWidgetItem(self.tree, [f"{key[1]}  ·  {len(idxs)}", ""])
                parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                parent.setExpanded(len(order) <= 2)
            for j in idxs:
                e = entries[j]
                label = e["title"]
                if e.get("episode") is not None and not e.get("nested"):
                    label = f"{e['episode']:>3}.  {label}"
                node = QTreeWidgetItem(parent or self.tree, [label, _fmt_duration(e.get("duration"))])
                node.setFlags(node.flags() | Qt.ItemIsUserCheckable)
                node.setCheckState(0, Qt.Checked if previous.get(j, True) else Qt.Unchecked)
                node.setToolTip(0, e["url"])
                self._items.append((node, j))
        self.tree.blockSignals(False)

    def _apply_filters(self, *_):
        self._build_tree()
        self._update_count()

    def _set_all(self, on: bool):
        for node, _ in self._items:
            node.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self._update_count()

    def selected(self) -> List[int]:
        return [j for node, j in self._items if node.checkState(0) == Qt.Checked]

    def _update_count(self, *_):
        n = len(self.selected())
        hidden = len(self.info["entries"]) - len(self._items)
        extra = f"  ({hidden} ausgeblendet)" if hidden else ""
        self.count.setText(f"{n} von {len(self._items)} ausgewählt{extra}")
        self.ok.setText(f"{n} hinzufügen")
        self.ok.setEnabled(n > 0)
        self.ok.updateGeometry()

    def _accept_all(self):
        self.choice = "all"
        self.accept()

    def _single(self):
        self.choice = "single"
        self.accept()


def confirm_playlist(parent, title: str, count: int, single_possible: bool) -> str:
    buttons = [("Abbrechen", "ghost", "cancel")]
    if single_possible:
        buttons.append(("Nur dieses Video", "glass", "single"))
    buttons.append((f"Alle {count} hinzufügen", "primary", "all"))
    key = message(parent, "Große Playlist erkannt",
                  f"„{title}“ enthält {count} Videos.\n\nSollen wirklich alle zur Warteschlange "
                  "hinzugefügt werden?", buttons, width=500)
    return key or "cancel"
