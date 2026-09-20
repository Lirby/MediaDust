"""MediaDust – yt-dlp-basierter Download-Manager im Glassmorphism-Stil.

Start: python main.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QActionGroup, QDesktopServices, QGuiApplication, QKeySequence,
                           QShortcut)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMenuBar,
                               QProgressBar, QVBoxLayout)

import platform_utils as pu
from queue_manager import ACTIVE, PRIORITY_TEXT, QueueManager, human_speed
from settings import Settings
from ui import style
from ui.dialogs import (AddLinksDialog, FormatDialog, FormatPicker, SeriesDialog, SettingsDialog, confirm_playlist,
                        extract_urls)
from ui.icons import app_icon, icon
from ui.queue_view import QueueView
from ui.titlebar import TitleBar
from ui import widgets as glass
from ui.widgets import FramelessResizer, GlassBackground, GlassButton, GlassPanel, message, try_native_blur
from updater import BinaryManager

VERSION = "0.2.2"
SERVER_NAME = f"MediaDust-{os.environ.get('USER') or os.environ.get('USERNAME') or 'user'}"


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        glass.NATIVE_BLUR = True        # immer starkes Blur (Rückfall auf QSS, falls nicht verfügbar)
        glass.NATIVE_STYLE = "blur"
        self.setWindowTitle("MediaDust")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(1120, 680)
        self.setMinimumSize(760, 440)

        self.qm = QueueManager(settings, self)
        self.ytdlp_version = ""
        self.ffmpeg_dir = ""
        self._quitting = False
        self.bin_manager = None

        self._build_ui()
        self._wire()
        self.resizer = FramelessResizer(self)


        QTimer.singleShot(0, self.start_setup)

    # ================================================================== UI
    def _build_ui(self):
        self.bg = GlassBackground()
        self.bg.setObjectName("Central")
        self.setCentralWidget(self.bg)
        root = QVBoxLayout(self.bg)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.titlebar = TitleBar("MediaDust", self)
        root.addWidget(self.titlebar)

        content = QVBoxLayout()
        content.setContentsMargins(20, 12, 20, 14)
        content.setSpacing(12)
        root.addLayout(content, 1)

        # --- Schnell-Hinzufügen
        quick = QHBoxLayout()
        quick.setSpacing(10)
        self.quick_edit = QLineEdit()
        self.quick_edit.setObjectName("QuickAdd")
        self.quick_edit.setPlaceholderText("Link einfügen und Enter drücken – YouTube, Vimeo, SoundCloud und 1800+ Seiten")
        self.quick_edit.setClearButtonEnabled(True)
        self.quick_edit.addAction(icon("link", "#9aa0c3"), QLineEdit.LeadingPosition)
        st = self.settings
        self.quick_fmt = FormatPicker(st.default_mode, st.default_quality, st.default_audio_bitrate,
                                      st.default_video_format, st.default_audio_format, compact=True)
        self.quick_btn = GlassButton("Hinzufügen", icon_name="plus", variant="primary")
        self.quick_btn.setFixedHeight(40)
        quick.addWidget(self.quick_edit, 1)
        quick.addWidget(self.quick_fmt)
        quick.addWidget(self.quick_btn)
        content.addLayout(quick)

        # --- Werkzeugleiste
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.btn_add = GlassButton("Links hinzufügen", icon_name="plus", compact=True)
        self.btn_start = GlassButton("Alle starten", icon_name="play", compact=True)
        self.btn_pause = GlassButton("Alle pausieren", icon_name="pause", compact=True)
        self.btn_clear = GlassButton("Fertige entfernen", icon_name="sweep", compact=True)
        self.btn_folder = GlassButton("Zielordner", icon_name="folder", compact=True)
        self.btn_settings = GlassButton(icon_name="gear", compact=True)
        self.btn_settings.setToolTip("Einstellungen")
        self.btn_settings.setFixedWidth(32)
        for b in (self.btn_add, self.btn_start, self.btn_pause, self.btn_clear, self.btn_folder):
            tools.addWidget(b)
        tools.addStretch(1)
        tools.addWidget(self.btn_settings)
        content.addLayout(tools)

        # --- Setup-Banner (yt-dlp/ffmpeg)
        self.banner = GlassPanel(radius=18, alpha=12)
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(20, 10, 16, 14)
        bl.setSpacing(12)
        self.banner_label = QLabel("Richte yt-dlp ein …")
        self.banner_label.setWordWrap(True)
        self.banner_bar = QProgressBar()
        self.banner_bar.setFixedSize(220, 8)
        self.banner_retry = GlassButton("Erneut versuchen", icon_name="retry", compact=True)
        self.banner_retry.hide()
        self.banner_close = GlassButton(icon_name="close", variant="ghost", compact=True)
        self.banner_close.setFixedWidth(30)
        self.banner_close.hide()
        bl.addWidget(self.banner_label, 1)
        bl.addWidget(self.banner_bar)
        bl.addWidget(self.banner_retry)
        bl.addWidget(self.banner_close)
        content.addWidget(self.banner)

        # --- Tabelle
        table_panel = GlassPanel(radius=22, alpha=8)
        tl = QVBoxLayout(table_panel)
        tl.setContentsMargins(12, 8, 12, 14)
        self.view = QueueView(self.qm.model)
        tl.addWidget(self.view)
        content.addWidget(table_panel, 1)

        # --- Statuszeile
        status = QHBoxLayout()
        status.setContentsMargins(4, 0, 4, 0)
        self.stat_label = QLabel("Bereit")
        self.stat_label.setProperty("muted", True)
        self.bin_label = QLabel("")
        self.bin_label.setProperty("muted", True)
        for l in (self.stat_label, self.bin_label):
            l.setStyleSheet("font-size: 12px;")
        status.addWidget(self.stat_label)
        status.addStretch(1)
        status.addWidget(self.bin_label)
        content.addLayout(status)

    def _wire(self):
        tb = self.titlebar
        tb.closeRequested.connect(self.close)
        tb.minimizeRequested.connect(self.showMinimized)
        tb.maximizeRequested.connect(self.toggle_maximize)

        self.quick_edit.returnPressed.connect(self.quick_add)
        self.quick_btn.clicked.connect(self.quick_add)
        self.btn_add.clicked.connect(lambda: self.open_add_dialog())
        self.btn_start.clicked.connect(self.qm.start_all)
        self.btn_pause.clicked.connect(self.qm.pause_all)
        self.btn_clear.clicked.connect(self.qm.clear_finished)
        self.btn_folder.clicked.connect(self.open_download_dir)
        self.btn_settings.clicked.connect(self.open_settings)
        self.banner_retry.clicked.connect(self.start_setup)
        self.banner_close.clicked.connect(self.banner.hide)

        self.view.actionClicked.connect(self._on_row_action)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.view.doubleClicked.connect(self._on_double_click)

        self.qm.playlistNeedsConfirm.connect(self._on_playlist_confirm)
        self.qm.statsChanged.connect(self._on_stats)
        self.qm.queueFinished.connect(self._on_queue_finished)
        self.qm.itemFailed.connect(self._on_item_failed)
        self.qm.itemFinished.connect(self._on_item_finished)

        local = Qt.WidgetWithChildrenShortcut
        QShortcut(QKeySequence.Paste, self.view, activated=self._paste_into_queue, context=local)
        QShortcut(QKeySequence.Delete, self.view, activated=self.remove_selected, context=local)
        QShortcut(QKeySequence(Qt.Key_Backspace), self.view, activated=self.remove_selected, context=local)
        if pu.IS_MAC:
            self._build_mac_menubar()
        else:
            QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.open_add_dialog())
            QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)
            QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.quit_app)
            QShortcut(QKeySequence("Ctrl+W"), self, activated=self.close)
        self._on_stats(0, 0, 0.0)

    def _build_mac_menubar(self):
        """Native macOS-Menüleiste (ohne Parent → bleibt auch bei verstecktem Fenster aktiv)."""
        bar = QMenuBar(None)
        self.menubar_global = bar

        def act(menu, text, slot, shortcut=None, role=None):
            a = menu.addAction(text)
            a.triggered.connect(lambda _=False: slot())
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            if role is not None:
                a.setMenuRole(role)
            return a

        # App-Menü: Qt verschiebt Einträge mit Rolle automatisch unter „MediaDust“
        app_menu = bar.addMenu("MediaDust")
        act(app_menu, "Über MediaDust", self.show_about, role=QAction.AboutRole)
        act(app_menu, "Einstellungen …", self.open_settings, "Ctrl+,", QAction.PreferencesRole)
        act(app_menu, "yt-dlp jetzt aktualisieren", self._menu_update_libs, role=QAction.ApplicationSpecificRole)
        act(app_menu, "MediaDust beenden", self.quit_app, "Ctrl+Q", QAction.QuitRole)

        m = bar.addMenu("Ablage")
        act(m, "Links hinzufügen …", lambda: self.open_add_dialog(), "Ctrl+N")
        act(m, "Link aus Zwischenablage einfügen", self._paste_into_queue, "Ctrl+Shift+V")
        m.addSeparator()
        act(m, "Zielordner öffnen", self.open_download_dir, "Ctrl+Shift+O")
        m.addSeparator()
        act(m, "Fenster schließen", self.close, "Ctrl+W")

        m = bar.addMenu("Bearbeiten")
        act(m, "Alles auswählen", self._select_all, "Ctrl+A")
        act(m, "Link kopieren", self._copy_selected_links, "Ctrl+C")
        m.addSeparator()
        act(m, "Auswahl entfernen", self.remove_selected)
        act(m, "Fertige entfernen", self.qm.clear_finished, "Ctrl+Shift+K")

        m = bar.addMenu("Downloads")
        act(m, "Alle starten", self.qm.start_all, "Ctrl+R")
        act(m, "Alle pausieren", self.qm.pause_all, "Ctrl+.")
        m.addSeparator()
        act(m, "Auswahl starten / fortsetzen", lambda: self.qm.resume(self.view.selected_ids()))
        act(m, "Auswahl pausieren", lambda: self.qm.pause(self.view.selected_ids()), "Ctrl+P")
        act(m, "Auswahl erneut versuchen", lambda: self.qm.retry(self.view.selected_ids()))
        act(m, "Auswahl abbrechen", lambda: self.qm.cancel(self.view.selected_ids()))
        act(m, "Format ändern …", lambda: self.change_format(self.view.selected_ids()), "Ctrl+E")
        prio = m.addMenu("Priorität")
        for value, key in ((1, "Ctrl+Up"), (0, None), (-1, "Ctrl+Down")):
            act(prio, PRIORITY_TEXT[value], lambda v=value: self.qm.set_priority(self.view.selected_ids(), v), key)
        m.addSeparator()
        act(m, "Im Finder anzeigen", self._reveal_selected, "Ctrl+Shift+R")

        m = bar.addMenu("Fenster")
        act(m, "Minimieren", self.showMinimized, "Ctrl+M")
        act(m, "Zoomen", self.toggle_maximize)
        m.addSeparator()
        act(m, "MediaDust", self.show_window, "Ctrl+1")

        m = bar.addMenu("Hilfe")
        act(m, "Unterstützte Seiten (yt-dlp)", lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md")))
        act(m, "Datenordner öffnen", lambda: pu.open_path(pu.data_dir()))

    def _menu_update_libs(self):
        if self.downloads_active():
            message(self, "Aktualisieren", "Bitte zuerst laufende Downloads pausieren – dann aktualisieren.")
            return
        self.update_libraries()

    def show_about(self):
        message(self, "Über MediaDust",
                f"MediaDust {VERSION}\n\nDownload-Manager auf Basis von yt-dlp.\n"
                f"yt-dlp: {self.ytdlp_version or '–'}\nffmpeg: {self.ffmpeg_dir or 'nicht verfügbar'}\n"
                f"Daten: {pu.data_dir()}")

    def remove_selected(self):
        self.qm.remove(self.view.selected_ids())

    def _select_all(self):
        self.show_window()
        self.view.selectAll()

    def _copy_selected_links(self):
        urls = [i.url for i in (self.qm.item(x) for x in self.view.selected_ids()) if i]
        if urls:
            self._copy_links(urls)

    def _reveal_selected(self):
        ids = self.view.selected_ids()
        if ids:
            self._reveal(ids[0])
        else:
            self.open_download_dir()

    # ================================================================== Setup (yt-dlp / ffmpeg)
    # --- Schnittstelle für den Update-Reiter der Einstellungen
    app_version = VERSION

    @property
    def ffmpeg_is_system(self) -> bool:
        return bool(self.ffmpeg_dir) and Path(self.ffmpeg_dir) != pu.ffmpeg_local_dir()

    def downloads_active(self) -> bool:
        return self.qm.active_count() > 0

    def update_libraries(self, ffmpeg: bool = False):
        """yt-dlp (und optional ffmpeg) sofort aktualisieren. Gibt den BinaryManager zurück."""
        if self.bin_manager and self.bin_manager.isRunning():
            return None
        self.qm.suspend()
        self.start_setup(force_update=True, refresh_ffmpeg=ffmpeg)
        return self.bin_manager

    def start_setup(self, force_update: bool = False, refresh_ffmpeg: bool = False):
        if self.bin_manager and self.bin_manager.isRunning():
            return
        self.banner.show()
        self.banner_retry.hide()
        self.banner_close.hide()
        self.banner_bar.show()
        self.banner_bar.setRange(0, 0)
        self.banner_label.setText("Richte yt-dlp ein …")
        st = self.settings
        week = 7 * 24 * 3600
        check_ffmpeg = st.ffmpeg_auto_update and (time.time() - st.ffmpeg_last_check > week)
        self.bin_manager = BinaryManager(st.auto_update or force_update, self,
                                         refresh_ffmpeg=refresh_ffmpeg, check_ffmpeg=check_ffmpeg)
        self.bin_manager.ffmpeg_checked.connect(self._on_ffmpeg_checked)
        bm = self.bin_manager
        bm.status.connect(self.banner_label.setText)
        bm.progress.connect(self._on_setup_progress)
        bm.ytdlp_version.connect(self._on_ytdlp_version)
        bm.ready.connect(self._on_setup_ready)
        bm.failed.connect(self._on_setup_failed)
        bm.warning.connect(self._on_setup_warning)
        bm.start()

    def _on_ffmpeg_checked(self):
        self.settings.ffmpeg_last_check = time.time()
        self.settings.save()

    def _on_setup_progress(self, value: int):
        if value < 0:
            self.banner_bar.setRange(0, 0)
        else:
            self.banner_bar.setRange(0, 100)
            self.banner_bar.setValue(value)

    def _on_ytdlp_version(self, v: str):
        self.ytdlp_version = v
        self._update_bin_label()

    def _update_bin_label(self):
        ff = "ffmpeg ✓" if self.ffmpeg_dir else "ffmpeg ✗"
        self.bin_label.setText(f"yt-dlp {self.ytdlp_version or '…'}  ·  {ff}  ·  MediaDust {VERSION}")

    def _on_setup_ready(self, ytdlp: str, ffmpeg_dir: str):
        self.ffmpeg_dir = ffmpeg_dir
        self._update_bin_label()
        self.qm.set_binaries(ytdlp, ffmpeg_dir)
        if not self.banner_close.isVisible():
            self.banner.hide()

    def _on_setup_failed(self, msg: str, gatekeeper: bool):
        self.banner.show()
        self.banner_bar.hide()
        self.banner_retry.show()
        self.banner_label.setText(("⚠︎ Gatekeeper-Blockade: " if gatekeeper else "⚠︎ ") + msg.split("\n")[0])
        self.banner_label.setToolTip(msg)
        if gatekeeper or self.isVisible():
            message(self, "yt-dlp konnte nicht eingerichtet werden", msg,
                    (("Schließen", "ghost", "close"), ("Erneut versuchen", "primary", "retry")))

    def _on_setup_warning(self, msg: str):
        self.banner.show()
        self.banner_bar.hide()
        self.banner_close.show()
        self.banner_label.setText("⚠︎ " + msg.split("\n")[0])
        self.banner_label.setToolTip(msg)

    # ================================================================== Aktionen
    def quick_add(self):
        urls = extract_urls(self.quick_edit.text())
        if not urls:
            self.quick_edit.setFocus()
            return
        mode, fmt, quality, bitrate = self.quick_fmt.values()
        n = self.qm.add_urls(urls, mode, quality, bitrate, container=fmt)
        self.quick_edit.clear()
        if n == 0:
            self.flash_status("Link ist bereits in der Warteschlange")

    def _paste_into_queue(self):
        urls = extract_urls(QGuiApplication.clipboard().text() or "")
        if len(urls) == 1:
            mode, fmt, quality, bitrate = self.quick_fmt.values()
            self.qm.add_urls(urls, mode, quality, bitrate, container=fmt)
        elif urls:
            self.open_add_dialog("\n".join(urls))

    def open_add_dialog(self, text: str = ""):
        self.show_window()
        if not text:
            clip = extract_urls(QGuiApplication.clipboard().text() or "")
            text = "\n".join(u for u in clip if not self.qm.has_url(u))
        dlg = AddLinksDialog(self.settings, text, self)
        if dlg.exec():
            mode, fmt, quality, bitrate = dlg.format.values()
            n = self.qm.add_urls(dlg.urls(), mode, quality, bitrate, dlg.folder.value(), dlg.start_now.isChecked(),
                                 container=fmt)
            self.flash_status(f"{n} Link(s) hinzugefügt")

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self, updates=self)
        if not dlg.exec():
            return
        changed = dlg.apply()
        s = self.settings
        fmt_keys = {"default_mode", "default_quality", "default_audio_bitrate", "default_video_format",
                    "default_audio_format"}
        if fmt_keys & set(changed):
            q = self.quick_fmt
            q.video_fmt.setCurrentIndex(max(0, q.video_fmt.findData(s.default_video_format)))
            q.audio_fmt.setCurrentIndex(max(0, q.audio_fmt.findData(s.default_audio_format)))
            q.quality.setCurrentIndex(max(0, q.quality.findData(s.default_quality)))
            q.bitrate.setCurrentIndex(max(0, q.bitrate.findData(s.default_audio_bitrate)))
            q.set_mode(s.default_mode)
        if "autostart" in changed:
            try:
                pu.set_autostart(s.autostart)
            except Exception as exc:
                message(self, "Autostart", f"Autostart konnte nicht geändert werden:\n{exc}")
        if {"max_parallel_video", "max_parallel_audio"} & set(changed):
            self.qm._pump()

    def open_download_dir(self):
        path = Path(self.settings.download_dir)
        path.mkdir(parents=True, exist_ok=True)
        pu.open_path(path)

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, e):
        if e.type() == QEvent.WindowStateChange:
            self.bg.rounded = not (self.isMaximized() or self.isFullScreen())
            self.bg.update()
            pu.set_native_corner_radius(self, self.bg.radius if self.bg.rounded else 0)
        super().changeEvent(e)

    def flash_status(self, text: str):
        self.stat_label.setText(text)
        QTimer.singleShot(3500, lambda: self._on_stats(*self._last_stats))

    # ================================================================== Queue-Ereignisse
    def _on_stats(self, active: int, waiting: int, speed: float):
        self._last_stats = (active, waiting, speed)
        total = self.qm.model.rowCount()
        done = sum(1 for i in self.qm.model.items if i.status == "finished")
        parts = [f"{total} Einträge", f"{done} fertig", f"{active} aktiv", f"{waiting} wartend"]
        if speed:
            parts.append(f"↓ {human_speed(speed)}")
        text = "  ·  ".join(parts)
        self.stat_label.setText(text)

    def _on_row_action(self, action: str, item_id: str):
        ids = [item_id]
        if action == "pause":
            self.qm.pause(ids)
        elif action in ("play",):
            self.qm.resume(ids)
        elif action == "retry":
            self.qm.retry(ids)
        elif action == "stop":
            self.qm.cancel(ids)
        elif action == "trash":
            self.qm.remove(ids)
        elif action == "folder":
            self._reveal(item_id)

    def _reveal(self, item_id: str):
        it = self.qm.item(item_id)
        if not it:
            return
        target = Path(it.filepath) if it.filepath else Path(it.target_dir)
        if not target.exists():
            target = Path(it.target_dir)
            target.mkdir(parents=True, exist_ok=True)
        pu.reveal_in_file_manager(target)

    def _on_double_click(self, index):
        it = self.qm.model.items[index.row()]
        if it.status == "finished" and it.filepath and Path(it.filepath).exists():
            pu.open_path(Path(it.filepath))
        elif it.status == "paused":
            self.qm.resume([it.id])

    def _context_menu(self, pos):
        idx = self.view.indexAt(pos)
        if idx.isValid() and not self.view.selectionModel().isRowSelected(idx.row(), idx.parent()):
            self.view.selectRow(idx.row())
        ids = self.view.selected_ids()
        menu = QMenu(self)
        if not ids:
            menu.addAction(icon("plus"), "Links hinzufügen …", self.open_add_dialog)
            menu.addAction(icon("clipboard"), "Aus Zwischenablage einfügen", self._paste_into_queue)
            menu.exec(self.view.viewport().mapToGlobal(pos))
            return
        items = [self.qm.item(i) for i in ids]
        statuses = {i.status for i in items if i}
        first = items[0]

        a = menu.addAction(icon("play"), "Starten / Fortsetzen", lambda: self.qm.resume(ids))
        a.setEnabled(bool(statuses & {"paused", "error", "canceled"}))
        a = menu.addAction(icon("pause"), "Pausieren", lambda: self.qm.pause(ids))
        a.setEnabled(bool(statuses & (ACTIVE | {"queued"})))
        menu.addAction(icon("retry"), "Erneut versuchen", lambda: self.qm.retry(ids))
        a = menu.addAction(icon("stop"), "Abbrechen", lambda: self.qm.cancel(ids))
        a.setEnabled(bool(statuses - {"finished", "canceled"}))
        menu.addSeparator()

        a = menu.addAction(icon("video"), "Format ändern …", lambda: self.change_format(ids))
        a.setEnabled(bool(statuses - ACTIVE))
        prio = menu.addMenu(icon("up"), "Priorität")
        group = QActionGroup(prio)
        for value in (1, 0, -1):
            act = prio.addAction(PRIORITY_TEXT[value])
            act.setCheckable(True)
            act.setChecked(first.priority == value)
            group.addAction(act)
            act.triggered.connect(lambda _=False, v=value: self.qm.set_priority(ids, v))

        menu.addSeparator()
        menu.addAction(icon("folder"), pu.file_manager_name(), lambda: self._reveal(first.id))
        a = menu.addAction(icon("file"), "Datei öffnen", lambda: pu.open_path(Path(first.filepath)))
        a.setEnabled(bool(first.filepath) and Path(first.filepath).exists())
        menu.addAction(icon("link"), "Link kopieren",
                       lambda: self._copy_links([i.url for i in items if i]))
        menu.addSeparator()
        menu.addAction(icon("trash"), "Aus Liste entfernen", lambda: self.qm.remove(ids))
        menu.exec(self.view.viewport().mapToGlobal(pos))

    def change_format(self, ids):
        items = [i for i in (self.qm.item(x) for x in ids) if i]
        if not items:
            return
        dlg = FormatDialog(items[0], len(items), self)
        if dlg.exec():
            mode, fmt, quality, bitrate = dlg.format.values()
            n = self.qm.set_format(ids, mode, fmt, quality, bitrate)
            self.flash_status(f"Format für {n} Eintrag/Einträge geändert")

    def _copy_links(self, urls):
        text = "\n".join(urls)
        QGuiApplication.clipboard().setText(text)

    def _on_playlist_confirm(self, item_id: str, title: str, count: int, single: bool):
        if not self.isVisible():
            self.show_window()
        info = self.qm.pending_playlist(item_id)
        if not info:
            self.qm.confirm_playlist(item_id, confirm_playlist(self, title, count, single))
            return
        dlg = SeriesDialog(info, single, self)
        dlg.exec()
        self.qm.confirm_playlist(item_id, dlg.choice, dlg.selected(), dlg.series_mode.isChecked(),
                                 dlg.name.text().strip())

    def _on_item_finished(self, item):
        if not self.isActiveWindow() and self.settings.after_complete == "notify":
            self.notify("Download fertig", item.title)

    def _on_item_failed(self, item):
        if not self.isActiveWindow():
            self.notify("Download fehlgeschlagen", f"{item.title}\n{item.error}")

    def _on_queue_finished(self):
        action = self.settings.after_complete
        if action == "notify":
            self.notify("MediaDust", "Alle Downloads abgeschlossen ✨")
        elif action == "open_folder":
            self.open_download_dir()
        elif action == "quit":
            self.notify("MediaDust", "Alle Downloads fertig – MediaDust wird beendet.")
            QTimer.singleShot(3000, self.quit_app)

    # ================================================================== Fenster
    def notify(self, title: str, text: str) -> None:
        """Mitteilung über die macOS-Mitteilungszentrale (andere Systeme: vorerst keine)."""
        if pu.IS_MAC:
            def esc(v: str) -> str:
                return v.replace("\\", "\\\\").replace('"', '\\"')
            script = f'display notification "{esc(text)}" with title "{esc(title)}"'
            try:
                subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass

    def show_window(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        if self._quitting:
            e.accept()
            return
        # Schließen beendet MediaDust; laufende Downloads werden beim nächsten Start fortgesetzt
        e.ignore()
        self.quit_app()

    def quit_app(self):
        if self._quitting:
            return
        self._quitting = True
        self.qm.shutdown()
        bm = self.bin_manager
        if bm is not None and bm.isRunning():
            # Setup läuft noch (Netzwerk) – kurz warten, sonst hart beenden, damit Qt nicht abbricht
            for sig in (bm.ready, bm.failed, bm.warning, bm.status, bm.progress, bm.ytdlp_version):
                try:
                    sig.disconnect()
                except (RuntimeError, TypeError):
                    pass
            if not bm.wait(3000):
                bm.terminate()
                bm.wait(1000)
        QApplication.instance().quit()

    def showEvent(self, e):
        super().showEvent(e)
        try_native_blur(self, self.bg)
        # Schatten nach dem ersten Zeichnen neu berechnen (verhindert dunkle Ecken)
        QTimer.singleShot(150, lambda: pu.set_native_corner_radius(self, self.bg.radius if self.bg.rounded else 0))


class Application(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("MediaDust")
        self.setApplicationDisplayName("MediaDust")
        self.setOrganizationName("MediaDust")
        self.setApplicationVersion(VERSION)
        self.setQuitOnLastWindowClosed(False)
        self.setStyle("Fusion")
        self.setStyleSheet(style.stylesheet())
        self.setWindowIcon(app_icon())
        self.window = None



def main() -> int:
    if pu.IS_MAC:
        os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")
    app = Application(sys.argv)

    # Nur eine Instanz: zweiter Start holt das bestehende Fenster nach vorne
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    server.listen(SERVER_NAME)

    settings = Settings.load()
    try:
        Path(settings.download_dir).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    win = MainWindow(settings)
    app.window = win

    def on_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(win.show_window)
            conn.disconnected.connect(conn.deleteLater)
    server.newConnection.connect(on_connection)

    win.show()

    grab = os.environ.get("MEDIADUST_DEBUG_GRAB")  # Entwicklung: Fenster als PNG rendern
    if grab:
        delay = int(os.environ.get("MEDIADUST_DEBUG_GRAB_DELAY", "4000"))
        QTimer.singleShot(delay, lambda: (app.activeModalWidget() or win).grab().save(grab))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
