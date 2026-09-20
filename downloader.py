"""Wrapper um die yt-dlp-Binary: Metadaten/Playlist-Auflösung und Downloads mit Fortschritts-Parsing."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

import platform_utils as pu
import series

PROG_PREFIX = "MDPROG|"
FILE_PREFIX = "MDFILE|"
TITLE_PREFIX = "MDTITLE|"

PROGRESS_TEMPLATE = (
    "download:" + PROG_PREFIX +
    "%(progress.status)s|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|"
    "%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s"
)

_PCT_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
_DEST_RE = re.compile(r"\[download\] Destination: (.+)$")
_ALREADY_RE = re.compile(r"\[download\] (.+) has already been downloaded")
_MERGE_RE = re.compile(r'\[Merger\] Merging formats into "(.+)"$')
_POST_RE = re.compile(r"^\[(Merger|ExtractAudio|VideoConvertor|FixupM3u8|FixupM4a|FixupStretched|"
                      r"FixupDuplicateMoov|FixupTimestamp|Metadata|EmbedThumbnail|MoveFiles)\]")


def _num(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_format_args(mode: str, quality: str, bitrate: str, container: str = "") -> list:
    if mode == "audio":
        fmt = container or "mp3"
        args = ["-f", "ba/b", "-x", "--audio-format", fmt]
        if fmt in ("flac", "wav", "best"):
            return args
        return args + ["--audio-quality", f"{bitrate}K"]

    fmt = container or "mp4"
    res = "" if quality == "best" else f"res:{quality},"
    if fmt == "webm":
        sort = res + "ext:webm:webm"
    elif fmt == "mkv":
        sort = res.rstrip(",") or "res"
    else:  # mp4 / mov → H.264/AAC bevorzugen, damit ohne Neukodierung verpackt werden kann
        sort = res + "ext:mp4:m4a"
    args = ["-f", "bv*+ba/b", "-S", sort, "--merge-output-format", fmt]
    if fmt in ("mp4", "mov", "mkv"):
        args += ["--remux-video", fmt]
    return args


def friendly_error(lines: list) -> str:
    errors = [l for l in lines if l.startswith("ERROR:")]
    text = (errors[-1] if errors else (lines[-1] if lines else "Unbekannter Fehler")).replace("ERROR: ", "")
    text = re.sub(r"^\[[^\]]+\]\s*[^:\s]*:\s*", "", text)   # "[youtube] abc123: " entfernen
    text = re.sub(r"\s*\(caused by .*\)$", "", text)
    low = text.lower()
    if "unsupported url" in low:
        return "Link wird nicht unterstützt"
    if "http error 404" in low or "does not exist" in low:
        return "Nicht gefunden (404) – Link prüfen"
    if "http error 403" in low:
        return "Zugriff verweigert (403)"
    if "confirm your age" in low or "age-restricted" in low or "age restricted" in low:
        return "Altersbeschränkt – Anmeldung nötig"
    if "private video" in low or "sign in" in low:
        return "Video privat oder Anmeldung nötig"
    if "video unavailable" in low or "not available" in low:
        return "Video nicht verfügbar"
    if "urlopen error" in low or "timed out" in low or "network" in low or "resolve" in low:
        return "Netzwerkfehler – Verbindung prüfen"
    if "ffmpeg" in low and "not found" in low:
        return "ffmpeg fehlt"
    if "permission denied" in low or "errno 13" in low:
        return "Keine Schreibrechte im Zielordner"
    if "no space left" in low:
        return "Kein Speicherplatz mehr"
    return text[:200]


def _is_nested(entry: dict, url: str) -> bool:
    """Eintrag ist selbst eine Playlist/Sammlung (z. B. Playlists eines YouTube-Kanals)."""
    if entry.get("_type") == "playlist":
        return True
    key = (entry.get("ie_key") or "").lower()
    if any(k in key for k in ("tab", "playlist", "collection", "channel", "category")):
        return True
    return "playlist?list=" in url


class ResolveWorker(QThread):
    """Ermittelt Titel bzw. Playlist-Einträge mit --flat-playlist."""
    resolved = Signal(str, dict)   # item_id, Info
    failed = Signal(str, str)

    def __init__(self, ytdlp: str, item_id: str, url: str, no_playlist: bool, parent=None):
        super().__init__(parent)
        self.ytdlp, self.item_id, self.url, self.no_playlist = ytdlp, item_id, url, no_playlist
        self._proc: Optional[subprocess.Popen] = None

    def run(self) -> None:
        cmd = [self.ytdlp, "--flat-playlist", "--dump-single-json", "--no-warnings", "--ignore-config",
               "--no-playlist" if self.no_playlist else "--yes-playlist", "--", self.url]
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True, encoding="utf-8", errors="replace",
                                          **pu.subprocess_kwargs())
            out, err = self._proc.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            pu.kill_process_tree(self._proc)
            self.failed.emit(self.item_id, "Zeitüberschreitung beim Abrufen der Infos")
            return
        except OSError as exc:
            self.failed.emit(self.item_id, f"yt-dlp nicht startbar: {exc}")
            return
        if self._proc.returncode != 0 or not out.strip():
            self.failed.emit(self.item_id, friendly_error(err.strip().splitlines()))
            return
        try:
            data = json.loads(out)
        except ValueError:
            self.failed.emit(self.item_id, "Ungültige Antwort von yt-dlp")
            return

        if data.get("_type") == "playlist":
            entries = []
            for e in data.get("entries") or []:
                if not e:
                    continue
                url = e.get("url") or e.get("webpage_url") or e.get("original_url")
                if url and not url.startswith("http") and e.get("ie_key") == "Youtube":
                    url = f"https://www.youtube.com/watch?v={e.get('id') or url}"
                if not url:
                    continue
                title = e.get("title") or url
                season, episode = series.parse_episode(title, e.get("season_number"), e.get("episode_number"))
                entries.append({
                    "url": url, "title": title, "season": season, "episode": episode,
                    "variant": series.is_variant(title), "extra": series.is_extra(title),
                    "nested": _is_nested(e, url), "duration": e.get("duration"),
                })
            # In echten Serien sind Einträge ohne Folgennummer meist Clips/Extras
            if sum(1 for e in entries if e["episode"] is not None) >= 2:
                for e in entries:
                    if e["episode"] is None and not e["nested"]:
                        e["extra"] = True
            title = data.get("title") or self.url
            parent = data.get("series") or data.get("playlist_title")
            # ARD liefert bei Staffel-Links nur „Staffel 1“ als Titel → Serienname aus der URL ergänzen
            if re.fullmatch(r"(Staffel|Season)\s*\d+", title, re.IGNORECASE):
                slug = re.search(r"/(?:serie|sendung)/([^/]+)/", self.url)
                parent = parent or (slug.group(1).replace("-", " ").title() if slug else "")
            info = {"type": "playlist", "title": title, "series": parent or title, "entries": entries}
        else:
            size = data.get("filesize") or data.get("filesize_approx") or 0
            info = {"type": "video", "title": data.get("title") or self.url,
                    "url": data.get("webpage_url") or self.url, "size": size,
                    "has_list": "list=" in self.url}
        self.resolved.emit(self.item_id, info)

    def cancel(self) -> None:
        if self._proc:
            pu.kill_process_tree(self._proc)


class DownloadWorker(QThread):
    progress = Signal(str, dict)          # item_id, {percent, speed, eta, size, status, title}
    done = Signal(str, bool, str, str)    # item_id, ok, message, filepath

    def __init__(self, ytdlp: str, ffmpeg_dir: str, item, parent=None):
        super().__init__(parent)
        self.ytdlp, self.ffmpeg_dir = ytdlp, ffmpeg_dir
        self.item_id = item.id
        self.url = item.url
        self.mode, self.quality, self.bitrate = item.mode, item.quality, item.audio_bitrate
        self.container = item.container
        self.out_name = item.out_name
        self.out_dir = Path(item.target_dir)
        # eigener Ordner für Zwischendateien → gleiche Videos in mehreren Formaten kollidieren nicht
        self.temp_dir = self.out_dir / ".mediadust-tmp" / item.id
        self._proc: Optional[subprocess.Popen] = None
        self.stop_reason: Optional[str] = None    # "pause" | "cancel"
        self.destinations: list = []

    def command(self) -> list:
        cmd = [self.ytdlp, "--newline", "--progress", "--no-simulate", "--ignore-config",
               "--no-playlist", "--continue", "--no-overwrites", "--no-colors",
               "--progress-template", PROGRESS_TEMPLATE,
               "--print", "before_dl:" + TITLE_PREFIX + "%(title)s",
               "--print", "after_move:" + FILE_PREFIX + "%(filepath)s",
               "-P", str(self.out_dir), "-P", f"temp:{self.temp_dir}",
               "-o", (self.out_name.replace("%", "%%") + ".%(ext)s") if self.out_name
               else "%(title).180B [%(id)s].%(ext)s",
               "--retries", "10", "--fragment-retries", "10"]
        if pu.IS_WIN:
            cmd.append("--windows-filenames")
        if self.ffmpeg_dir:
            cmd += ["--ffmpeg-location", self.ffmpeg_dir]
        cmd += build_format_args(self.mode, self.quality, self.bitrate, self.container)
        cmd += ["--", self.url]
        return cmd

    def run(self) -> None:
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.done.emit(self.item_id, False, f"Zielordner nicht beschreibbar: {exc}", "")
            return
        try:
            self._proc = subprocess.Popen(self.command(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          text=True, encoding="utf-8", errors="replace", bufsize=1,
                                          **pu.subprocess_kwargs())
        except PermissionError:
            self.done.emit(self.item_id, False, "yt-dlp blockiert (Berechtigung/Gatekeeper)", "")
            return
        except OSError as exc:
            self.done.emit(self.item_id, False, f"yt-dlp nicht startbar: {exc}", "")
            return

        tail: list = []
        filepath = ""
        phase = 0
        multi = self.mode == "video"
        for raw in self._proc.stdout:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            if line.startswith(PROG_PREFIX):
                self._handle_progress(line, phase, multi)
                continue
            if line.startswith(TITLE_PREFIX):
                self.progress.emit(self.item_id, {"title": line[len(TITLE_PREFIX):]})
                continue
            if line.startswith(FILE_PREFIX):
                filepath = line[len(FILE_PREFIX):]
                continue
            tail = (tail + [line])[-30:]
            m = _DEST_RE.search(line)
            if m:
                phase += 1
                self.destinations.append(m.group(1))
                continue
            m = _ALREADY_RE.search(line)
            if m:
                filepath = filepath or m.group(1)
                self.progress.emit(self.item_id, {"percent": 100.0, "status": "processing"})
                continue
            m = _MERGE_RE.search(line)
            if m:
                self.destinations.append(m.group(1))
            if _POST_RE.match(line):
                self.progress.emit(self.item_id, {"status": "processing", "percent": 100.0,
                                                  "speed": 0, "eta": None})
                continue
            m = _PCT_RE.search(line)
            if m:
                self.progress.emit(self.item_id, {"percent": float(m.group(1))})

        code = self._proc.wait()
        if self.stop_reason != "pause":  # beim Pausieren bleiben Teildateien zum Fortsetzen liegen
            self._remove_temp_dir()
        if self.stop_reason:
            if self.stop_reason == "cancel":
                self._cleanup_partials()
            self.done.emit(self.item_id, False, self.stop_reason, "")
        elif code == 0:
            self.done.emit(self.item_id, True, "", filepath)
        else:
            self.done.emit(self.item_id, False, friendly_error(tail), "")

    def _remove_temp_dir(self) -> None:
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        try:
            self.temp_dir.parent.rmdir()  # nur wenn leer
        except OSError:
            pass

    def _handle_progress(self, line: str, phase: int, multi: bool) -> None:
        parts = line[len(PROG_PREFIX):].split("|")
        if len(parts) < 6:
            return
        status, done, total, estimate, speed, eta = parts[:6]
        done_n, total_n = _num(done), _num(total) or _num(estimate)
        info: dict = {"status": "downloading", "speed": _num(speed) or 0, "eta": _num(eta)}
        if done_n is not None and total_n:
            info["percent"] = min(100.0, done_n * 100.0 / total_n)
            info["size"] = total_n
        if multi and phase > 1:
            info["phase"] = phase
        if status == "finished":
            info["percent"] = 100.0
        self.progress.emit(self.item_id, info)

    def stop(self, reason: str) -> None:
        self.stop_reason = reason
        if self._proc:
            pu.kill_process_tree(self._proc)

    def _cleanup_partials(self) -> None:
        """Entfernt Teil-Dateien (.part/.ytdl/Fragmente) und Zwischenformate (*.f137.mp4)."""
        for dest in self.destinations:
            base = Path(dest)
            leftovers = [Path(str(base) + ".part"), Path(str(base) + ".ytdl")]
            leftovers += list(base.parent.glob(glob_escape(base.name) + ".part-Frag*"))
            if _INTERMEDIATE_RE.search(base.name):
                leftovers.append(base)
            for f in leftovers:
                try:
                    f.unlink()
                except OSError:
                    pass


_INTERMEDIATE_RE = re.compile(r"\.f[\w-]+\.\w+$")


def glob_escape(name: str) -> str:
    return re.sub(r"([\[\]*?])", r"[\1]", name)
