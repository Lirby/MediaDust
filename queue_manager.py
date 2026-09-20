"""Warteschlangen-Logik, Scheduling paralleler Downloads, Tabellenmodell und Persistenz."""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QTimer, Signal

import series
from downloader import DownloadWorker, ResolveWorker
from platform_utils import data_dir

STATUS_TEXT = {
    "resolving": "Analysiere …",
    "confirm": "Wartet auf Bestätigung",
    "queued": "Wartend",
    "downloading": "Lädt",
    "processing": "Verarbeite",
    "paused": "Pausiert",
    "finished": "Fertig",
    "error": "Fehler",
    "canceled": "Abgebrochen",
}
ACTIVE = {"downloading", "processing"}
PRIORITY_TEXT = {1: "Hoch", 0: "Normal", -1: "Niedrig"}
MAX_RESOLVERS = 4


@dataclass
class DownloadItem:
    url: str
    mode: str = "video"
    quality: str = "1080"
    audio_bitrate: str = "192"
    container: str = ""              # mp4/mkv/webm/mov bzw. mp3/m4a/opus/ogg/flac/wav/best
    target_dir: str = ""
    title: str = ""
    status: str = "resolving"
    progress: float = 0.0
    size: float = 0.0
    priority: int = 0
    filepath: str = ""
    error: str = ""
    no_playlist: bool = False
    out_name: str = ""               # fester Dateiname ohne Endung (Serien-Modus)
    season: Optional[int] = None
    episode: Optional[int] = None
    hold: bool = False               # nach der Analyse pausiert lassen
    added_at: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    # flüchtig (nicht gespeichert)
    speed: float = 0.0
    eta: Optional[float] = None
    phase: int = 0

    TRANSIENT = ("speed", "eta", "phase")

    def to_json(self) -> dict:
        d = asdict(self)
        for k in self.TRANSIENT:
            d.pop(k, None)
        return d

    @classmethod
    def from_json(cls, d: dict) -> "DownloadItem":
        known = {f.name for f in fields(cls)} - set(cls.TRANSIENT)
        return cls(**{k: v for k, v in d.items() if k in known})

    @property
    def ext(self) -> str:
        return self.container or ("mp3" if self.mode == "audio" else "mp4")

    @property
    def format_label(self) -> str:
        if self.mode == "audio":
            if self.ext == "best":
                return "Audio · Original"
            if self.ext in ("flac", "wav"):
                return self.ext.upper()
            return f"{self.ext.upper()} · {self.audio_bitrate}k"
        return f"{self.ext.upper()} · " + ("Beste" if self.quality == "best" else f"{self.quality}p")

    @property
    def status_label(self) -> str:
        if self.status == "error" and self.error:
            return f"Fehler: {self.error}"
        if self.status == "downloading" and self.mode == "video" and self.phase > 1:
            return "Lädt (Audio)"
        return STATUS_TEXT.get(self.status, self.status)


def human_size(n: float) -> str:
    if not n:
        return "–"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"


def human_speed(n: float) -> str:
    return "–" if not n else human_size(n) + "/s"


def human_eta(sec: Optional[float]) -> str:
    if sec is None or sec < 0:
        return "–"
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def safe_folder_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name[:120] or "Playlist"


class QueueModel(QAbstractTableModel):
    COLUMNS = ["Titel", "Format", "Status", "Fortschritt", "Geschw.", "Restzeit", "Größe", ""]
    COL_TITLE, COL_FORMAT, COL_STATUS, COL_PROGRESS, COL_SPEED, COL_ETA, COL_SIZE, COL_ACTIONS = range(8)
    ItemRole = Qt.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[DownloadItem] = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self.items[index.row()]
        col = index.column()
        if role == self.ItemRole:
            return item
        if role == Qt.DisplayRole:
            if col == self.COL_TITLE:
                prefix = {1: "▲ ", -1: "▼ "}.get(item.priority, "")
                return prefix + (item.title or item.url)
            if col == self.COL_FORMAT:
                return item.format_label
            if col == self.COL_STATUS:
                return item.status_label
            if col == self.COL_PROGRESS:
                return item.progress
            if col == self.COL_SPEED:
                return human_speed(item.speed) if item.status == "downloading" else "–"
            if col == self.COL_ETA:
                return human_eta(item.eta) if item.status == "downloading" else "–"
            if col == self.COL_SIZE:
                return human_size(item.size)
        if role == Qt.ToolTipRole:
            if col == self.COL_TITLE:
                return f"{item.title}\n{item.url}" + (f"\n{item.filepath}" if item.filepath else "")
            if col == self.COL_STATUS and item.error:
                return item.error
        if role == Qt.TextAlignmentRole and col in (self.COL_SPEED, self.COL_ETA, self.COL_SIZE):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def row_of(self, item_id: str) -> int:
        for i, it in enumerate(self.items):
            if it.id == item_id:
                return i
        return -1

    def refresh_row(self, row: int) -> None:
        if 0 <= row < len(self.items):
            self.dataChanged.emit(self.index(row, 0), self.index(row, self.columnCount() - 1))

    def insert(self, row: int, new_items: List[DownloadItem]) -> None:
        if not new_items:
            return
        self.beginInsertRows(QModelIndex(), row, row + len(new_items) - 1)
        self.items[row:row] = new_items
        self.endInsertRows()

    def remove_row(self, row: int) -> None:
        self.beginRemoveRows(QModelIndex(), row, row)
        del self.items[row]
        self.endRemoveRows()


class QueueManager(QObject):
    playlistNeedsConfirm = Signal(str, str, int, bool)   # item_id, Titel, Anzahl, Einzelvideo möglich
    # Details der wartenden Playlist über pending_playlist(item_id)
    itemFinished = Signal(object)
    itemFailed = Signal(object)
    queueFinished = Signal()
    statsChanged = Signal(int, int, float)               # aktiv, wartend, Gesamtgeschwindigkeit

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.model = QueueModel(self)
        self.ytdlp = ""
        self.ffmpeg_dir = ""
        self.ready = False
        self.workers: Dict[str, DownloadWorker] = {}
        self.resolvers: Dict[str, ResolveWorker] = {}
        self._finished_since_idle = 0
        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self.save)
        self.path: Path = data_dir() / "queue.json"
        self.load()

    # ------------------------------------------------------------------ Persistenz
    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        items = []
        for d in raw.get("items", []):
            try:
                it = DownloadItem.from_json(d)
            except TypeError:
                continue
            if it.status in ACTIVE:
                it.status = "queued" if self.settings.autostart_downloads else "paused"
            elif it.status == "confirm":
                it.status = "resolving"
            items.append(it)
        self.model.insert(0, items)

    def save(self) -> None:
        data = {"version": 1, "items": [it.to_json() for it in self.model.items]}
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            print(f"[MediaDust] Queue konnte nicht gespeichert werden: {exc}")

    def _changed(self, row: int = -1) -> None:
        if row >= 0:
            self.model.refresh_row(row)
        self._save_timer.start()
        self._emit_stats()

    def _emit_stats(self) -> None:
        items = self.model.items
        active = sum(1 for i in items if i.status in ACTIVE)
        waiting = sum(1 for i in items if i.status in ("queued", "resolving"))
        speed = sum(i.speed for i in items if i.status == "downloading")
        self.statsChanged.emit(active, waiting, speed)

    # ------------------------------------------------------------------ Zugriff
    def item(self, item_id: str) -> Optional[DownloadItem]:
        row = self.model.row_of(item_id)
        return self.model.items[row] if row >= 0 else None

    def has_url(self, url: str) -> bool:
        return any(i.url == url and i.status not in ("canceled",) for i in self.model.items)

    def suspend(self) -> None:
        """Keine neuen Downloads starten (z. B. während yt-dlp aktualisiert wird)."""
        self.ready = False

    def set_binaries(self, ytdlp: str, ffmpeg_dir: str) -> None:
        self.ytdlp, self.ffmpeg_dir, self.ready = ytdlp, ffmpeg_dir, True
        self._pump()

    # ------------------------------------------------------------------ Hinzufügen
    def add_urls(self, urls: List[str], mode: str, quality: str, bitrate: str,
                 target_dir: Optional[str] = None, start: bool = True, container: str = "") -> int:
        if not container:
            s = self.settings
            container = s.default_audio_format if mode == "audio" else s.default_video_format
        added = []
        for url in urls:
            url = url.strip()
            if not url or self.has_url(url):
                continue
            added.append(DownloadItem(url=url, mode=mode, quality=quality, audio_bitrate=bitrate, container=container,
                                      target_dir=target_dir or self.settings.download_dir,
                                      title=url, status="resolving", hold=not start))
        self.model.insert(len(self.model.items), added)
        self._changed()
        self._pump()
        return len(added)

    # ------------------------------------------------------------------ Auflösen
    def _start_resolvers(self) -> None:
        if not self.ready:
            return
        for it in self.model.items:
            if len(self.resolvers) >= MAX_RESOLVERS:
                break
            if it.status == "resolving" and it.id not in self.resolvers:
                w = ResolveWorker(self.ytdlp, it.id, it.url, it.no_playlist, self)
                w.resolved.connect(self._on_resolved)
                w.failed.connect(self._on_resolve_failed)
                w.finished.connect(lambda iid=it.id: self._resolver_done(iid))
                self.resolvers[it.id] = w
                w.start()

    def _resolver_done(self, item_id: str) -> None:
        w = self.resolvers.pop(item_id, None)
        if w:
            w.deleteLater()
        self._pump()

    def _after_resolve_status(self, it: DownloadItem) -> str:
        hold = it.hold or not self.settings.autostart_downloads
        it.hold = False
        return "paused" if hold else "queued"

    def _on_resolved(self, item_id: str, info: dict) -> None:
        row = self.model.row_of(item_id)
        if row < 0 or self.model.items[row].status != "resolving":
            return
        it = self.model.items[row]
        if info["type"] == "video":
            it.title = info["title"]
            it.size = info.get("size") or 0
            it.status = self._after_resolve_status(it)
            self._changed(row)
            return
        entries = info["entries"]
        it.title = f"Playlist: {info['title']} ({len(entries)} Einträge)"
        if not entries:
            it.status, it.error = "error", "Playlist ist leer"
            self._changed(row)
            return
        looks_like_series = sum(1 for e in entries if e.get("episode") is not None) >= 2
        needs_choice = any(e.get("variant") or e.get("extra") for e in entries)
        if looks_like_series or needs_choice or len(entries) > self.settings.playlist_confirm_threshold:
            it.status = "confirm"
            it._pending_playlist = info  # type: ignore[attr-defined]
            self._changed(row)
            single_possible = "v=" in it.url or "youtu.be/" in it.url
            self.playlistNeedsConfirm.emit(item_id, info["title"], len(entries), single_possible)
        else:
            self._expand(row, info)

    def _on_resolve_failed(self, item_id: str, message: str) -> None:
        row = self.model.row_of(item_id)
        if row >= 0 and self.model.items[row].status == "resolving":
            it = self.model.items[row]
            it.status, it.error = "error", message
            self._changed(row)
            self.itemFailed.emit(it)

    def pending_playlist(self, item_id: str) -> Optional[dict]:
        it = self.item(item_id)
        return getattr(it, "_pending_playlist", None) if it else None

    def confirm_playlist(self, item_id: str, choice: str, selected: Optional[List[int]] = None,
                         series_mode: bool = False, series_name: str = "") -> None:
        """choice: 'all' | 'single' | 'cancel'; selected = Indizes der gewählten Einträge."""
        row = self.model.row_of(item_id)
        if row < 0:
            return
        it = self.model.items[row]
        info = getattr(it, "_pending_playlist", None)
        if choice == "all" and info:
            self._expand(row, info, selected, series_mode, series_name)
        elif choice == "single":
            it.no_playlist, it.status, it.title = True, "resolving", it.url
            self._changed(row)
            self._pump()
        else:
            self.model.remove_row(row)
            self._changed()

    def _expand(self, row: int, info: dict, selected: Optional[List[int]] = None,
                series_mode: bool = False, series_name: str = "") -> None:
        parent = self.model.items[row]
        name = series_name or info.get("series") or info["title"]
        base = Path(parent.target_dir) / safe_folder_name(name)
        status = self._after_resolve_status(parent)
        parent.hold = False
        entries = info["entries"]
        indices = selected if selected is not None else range(len(entries))
        new_items = []
        for i in indices:
            e = entries[i]
            item = DownloadItem(url=e["url"], title=e["title"], mode=parent.mode, quality=parent.quality,
                                container=parent.container, audio_bitrate=parent.audio_bitrate,
                                target_dir=str(base), status=status, priority=parent.priority,
                                no_playlist=True, season=e.get("season"), episode=e.get("episode"))
            if e.get("nested"):  # Unter-Playlist → selbst wieder auflösen
                item.status, item.no_playlist, item.target_dir = "resolving", False, parent.target_dir
                item.title = item.url
            elif series_mode:
                folder = series.season_folder(e.get("season")) if not e.get("extra") else "Extras"
                item.target_dir = str(base / folder)
                item.out_name = series.episode_filename(name, e.get("season"), e.get("episode"), e["title"])
            new_items.append(item)
        self.model.remove_row(row)
        self.model.insert(row, new_items)
        self._changed()
        self._pump()

    # ------------------------------------------------------------------ Scheduling
    def _pump(self) -> None:
        self._start_resolvers()
        if not self.ready:
            return
        # getrennte Limits für Video und Musik
        limits = {"video": self.settings.max_parallel_video, "audio": self.settings.max_parallel_audio}
        running = {"video": 0, "audio": 0}
        for w in self.workers.values():
            running["audio" if w.mode == "audio" else "video"] += 1
        candidates = sorted(
            (i for i in enumerate(self.model.items) if i[1].status == "queued" and i[1].id not in self.workers),
            key=lambda p: (-p[1].priority, p[0]))
        for row, it in candidates:
            kind = "audio" if it.mode == "audio" else "video"
            if running[kind] < limits[kind]:
                running[kind] += 1
                self._start_download(row, it)
        self._check_idle()

    def _start_download(self, row: int, it: DownloadItem) -> None:
        w = DownloadWorker(self.ytdlp, self.ffmpeg_dir, it, self)
        w.progress.connect(self._on_progress)
        w.done.connect(self._on_done)
        w.finished.connect(w.deleteLater)
        self.workers[it.id] = w
        it.status, it.error, it.speed, it.eta, it.phase = "downloading", "", 0.0, None, 0
        self._changed(row)
        w.start()

    def _on_progress(self, item_id: str, info: dict) -> None:
        row = self.model.row_of(item_id)
        if row < 0:
            return
        it = self.model.items[row]
        if it.status not in ACTIVE:
            return
        if "title" in info and info["title"]:
            it.title = info["title"]
        if "phase" in info and info["phase"] != it.phase:
            it.phase = info["phase"]
        if "percent" in info:
            it.progress = info["percent"]
        if "speed" in info:
            it.speed = info["speed"]
        if "eta" in info:
            it.eta = info["eta"]
        if info.get("size"):
            it.size = info["size"] if it.phase <= 1 else max(it.size, info["size"])
        if info.get("status"):
            it.status = info["status"]
        self.model.refresh_row(row)
        self._emit_stats()

    def _on_done(self, item_id: str, ok: bool, message: str, filepath: str) -> None:
        self.workers.pop(item_id, None)
        row = self.model.row_of(item_id)
        if row >= 0:
            it = self.model.items[row]
            it.speed, it.eta = 0.0, None
            if ok:
                it.status, it.progress, it.error = "finished", 100.0, ""
                if filepath:
                    it.filepath = filepath
                    try:
                        it.size = Path(filepath).stat().st_size
                    except OSError:
                        pass
                self._finished_since_idle += 1
                self.itemFinished.emit(it)
            elif message == "pause":
                it.status = "paused"
            elif message == "cancel":
                it.status, it.progress = "canceled", 0.0
            else:
                it.status, it.error = "error", message
                self.itemFailed.emit(it)
            self._changed(row)
        self._pump()

    def _check_idle(self) -> None:
        busy = any(i.status in ACTIVE | {"queued", "resolving", "confirm"} for i in self.model.items)
        if not busy and not self.workers and self._finished_since_idle:
            self._finished_since_idle = 0
            self.queueFinished.emit()

    # ------------------------------------------------------------------ Aktionen
    def pause(self, ids: List[str]) -> None:
        for iid in ids:
            it = self.item(iid)
            if not it:
                continue
            if iid in self.workers:
                self.workers[iid].stop("pause")
            elif it.status == "queued":
                it.status = "paused"
                self._changed(self.model.row_of(iid))

    def resume(self, ids: List[str]) -> None:
        for iid in ids:
            it = self.item(iid)
            if it and it.status in ("paused", "error", "canceled") and iid not in self.workers:
                if it.status == "canceled":
                    it.progress = 0.0
                # nie aufgelöste Einträge (Fehler bei der Analyse) erneut analysieren
                it.status = "resolving" if it.title == it.url else "queued"
                it.error = ""
                self._changed(self.model.row_of(iid))
        self._pump()

    def retry(self, ids: List[str]) -> None:
        for iid in ids:
            it = self.item(iid)
            if not it or iid in self.workers:
                continue
            it.error, it.speed, it.eta = "", 0.0, None
            if it.status == "finished":
                it.progress = 0.0
            # nie aufgelöste Einträge erneut analysieren
            it.status = "resolving" if it.title == it.url else "queued"
            self._changed(self.model.row_of(iid))
        self._pump()

    def cancel(self, ids: List[str]) -> None:
        for iid in ids:
            it = self.item(iid)
            if not it:
                continue
            if iid in self.workers:
                self.workers[iid].stop("cancel")
            elif iid in self.resolvers:
                it.status = "canceled"
                self.resolvers[iid].cancel()
                self._changed(self.model.row_of(iid))
            elif it.status in ("queued", "paused", "error", "resolving", "confirm"):
                it.status, it.progress = "canceled", 0.0
                self._changed(self.model.row_of(iid))

    def remove(self, ids: List[str]) -> None:
        for iid in ids:
            if iid in self.workers:
                w = self.workers.pop(iid)
                w.stop("cancel")
            if iid in self.resolvers:
                self.resolvers[iid].cancel()
            row = self.model.row_of(iid)
            if row >= 0:
                self.model.remove_row(row)
        self._changed()
        self._pump()

    def set_format(self, ids: List[str], mode: str, container: str, quality: str, bitrate: str) -> int:
        """Ändert das Zielformat nicht laufender Einträge; fertige werden neu geladen."""
        changed = 0
        for iid in ids:
            it = self.item(iid)
            if not it or iid in self.workers or it.status in ACTIVE:
                continue
            it.mode, it.container, it.quality, it.audio_bitrate = mode, container, quality, bitrate
            if it.status == "finished":
                it.status, it.progress, it.filepath = "queued", 0.0, ""
            changed += 1
            self._changed(self.model.row_of(iid))
        self._pump()
        return changed

    def set_priority(self, ids: List[str], prio: int) -> None:
        for iid in ids:
            it = self.item(iid)
            if it:
                it.priority = prio
                self._changed(self.model.row_of(iid))
        self._pump()

    def pause_all(self) -> None:
        self.pause([i.id for i in self.model.items if i.status in ACTIVE | {"queued"}])

    def start_all(self) -> None:
        self.resume([i.id for i in self.model.items if i.status in ("paused",)])

    def clear_finished(self) -> None:
        self.remove([i.id for i in self.model.items if i.status in ("finished", "canceled")])

    def active_count(self) -> int:
        return len(self.workers)

    def shutdown(self) -> None:
        """Beim Beenden: laufende Downloads stoppen (werden beim nächsten Start fortgesetzt)."""
        for w in list(self.workers.values()):
            w.stop("pause")
        for r in list(self.resolvers.values()):
            r.cancel()
        for w in list(self.workers.values()) + list(self.resolvers.values()):
            w.wait(3000)
        for it in self.model.items:
            if it.status in ACTIVE or it.id in self.workers:
                it.status = "queued"
        self.save()
