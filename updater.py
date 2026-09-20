"""Download & Update von yt-dlp und ffmpeg (plattformabhängig), läuft in einem QThread."""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal

import platform_utils as pu

USER_AGENT = "MediaDust/0.2 (+https://github.com/yt-dlp/yt-dlp)"


def _vtuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def latest_ytdlp_tag() -> str:
    """Neueste Release-Version über die Weiterleitung von /releases/latest (ohne API-Limit)."""
    req = urllib.request.Request(pu.YTDLP_LATEST_URL, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as resp:
            final = resp.geturl()
    except (urllib.error.URLError, OSError) as exc:
        raise SetupError(f"Update-Prüfung fehlgeschlagen: {exc}") from exc
    return final.rstrip("/").rsplit("/tag/", 1)[-1] if "/tag/" in final else ""


def ffmpeg_remote_id() -> str:
    """Kennung der neuesten angebotenen ffmpeg-Version (Ziel-URL der Weiterleitung + ETag/Datum)."""
    src = pu.ffmpeg_sources()
    url = src["urls"]["ffmpeg"] if src["kind"] == "zip-per-tool" else src["url"]
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as resp:
            final = resp.geturl()
            tag = resp.headers.get("ETag") or resp.headers.get("Last-Modified") or ""
    except (urllib.error.URLError, OSError) as exc:
        raise SetupError(f"keine Verbindung: {exc}") from exc
    # Martin-Riedl-URLs enthalten die Version im Pfad; bei GitHub ändert sich das ETag
    return final.split("?")[0] + ("" if pu.IS_MAC else "|" + tag)


class SetupError(Exception):
    def __init__(self, message: str, gatekeeper: bool = False):
        super().__init__(message)
        self.gatekeeper = gatekeeper


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # gebündelte CA-Zertifikate (wichtig im PyInstaller-Bundle)
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url: str, progress: Optional[Callable[[int, int], None]] = None, timeout: int = 30) -> tuple:
    """Lädt eine URL in den Speicher. Rückgabe: (bytes, finale URL)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            buf = io.BytesIO()
            done = 0
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                buf.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
            return buf.getvalue(), resp.geturl()
    except urllib.error.HTTPError as exc:
        raise SetupError(f"Download fehlgeschlagen (HTTP {exc.code}): {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SetupError(f"Keine Verbindung zu {urllib.request.urlparse(url).netloc}: {exc}") from exc


def _atomic_write(target: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=target.name + ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def run_binary(path: Path, args: list, timeout: int = 90) -> subprocess.CompletedProcess:
    """Führt eine Binary aus und übersetzt Gatekeeper-/Rechteprobleme in SetupError."""
    try:
        res = subprocess.run([str(path)] + args, capture_output=True, text=True, timeout=timeout,
                             **pu.subprocess_kwargs())
    except PermissionError as exc:
        raise SetupError(pu.gatekeeper_hint(path), gatekeeper=True) from exc
    except OSError as exc:
        raise SetupError(f"{path.name} konnte nicht gestartet werden: {exc}", gatekeeper=pu.IS_MAC) from exc
    except subprocess.TimeoutExpired as exc:
        raise SetupError(f"{path.name} reagiert nicht (Timeout).") from exc
    # SIGKILL (-9) direkt beim Start ist auf macOS das typische Zeichen einer Gatekeeper-Blockade
    if res.returncode in (-9, 137) and pu.IS_MAC:
        raise SetupError(pu.gatekeeper_hint(path), gatekeeper=True)
    return res


class BinaryManager(QThread):
    status = Signal(str)
    progress = Signal(int)            # 0..100, -1 = unbestimmt
    ytdlp_version = Signal(str)
    ready = Signal(str, str)          # yt-dlp-Pfad, ffmpeg-Ordner ("" wenn nicht verfügbar)
    failed = Signal(str, bool)        # Meldung, Gatekeeper-Problem?
    warning = Signal(str)

    ffmpeg_checked = Signal()         # ffmpeg-Update-Prüfung ist gelaufen (für „zuletzt geprüft“)

    def __init__(self, auto_update: bool = True, parent=None, refresh_ffmpeg: bool = False,
                 check_ffmpeg: bool = False):
        super().__init__(parent)
        self.auto_update = auto_update
        self.refresh_ffmpeg = refresh_ffmpeg   # eigene ffmpeg-Kopie sofort neu herunterladen
        self.check_ffmpeg = check_ffmpeg       # prüfen, ob es eine neuere ffmpeg-Version gibt

    # ------------------------------------------------------------------ Thread
    def run(self) -> None:
        try:
            ytdlp = self.ensure_ytdlp()
        except SetupError as exc:
            self.failed.emit(str(exc), exc.gatekeeper)
            return
        except Exception as exc:  # unerwartet
            self.failed.emit(f"Unerwarteter Fehler beim Einrichten von yt-dlp: {exc}", False)
            return

        ffmpeg_dir = ""
        try:
            ffmpeg_dir = str(self.ensure_ffmpeg())
        except SetupError as exc:
            self.warning.emit("ffmpeg nicht verfügbar – Zusammenführen/MP3 funktioniert nicht.\n" + str(exc))
        except Exception as exc:
            self.warning.emit(f"ffmpeg-Einrichtung fehlgeschlagen: {exc}")

        self.progress.emit(100)
        self.status.emit("Bereit")
        self.ready.emit(str(ytdlp), ffmpeg_dir)

    def _progress_cb(self, label: str):
        def cb(done: int, total: int) -> None:
            if total:
                self.progress.emit(int(done * 100 / total))
                self.status.emit(f"{label} … {done / 1048576:.1f} / {total / 1048576:.1f} MB")
            else:
                self.progress.emit(-1)
                self.status.emit(f"{label} … {done / 1048576:.1f} MB")
        return cb

    # ------------------------------------------------------------------ yt-dlp
    def ensure_ytdlp(self) -> Path:
        path = pu.ytdlp_path()
        if not path.is_file():
            self._install_ytdlp()
        try:
            pu.prepare_binary(path, path.parent if pu.ytdlp_is_bundle() else None)
        except OSError as exc:
            raise SetupError(f"Keine Berechtigung, {path} ausführbar zu machen: {exc}") from exc

        self.status.emit("Prüfe yt-dlp (erster Start kann etwas dauern)")
        self.progress.emit(-1)
        version = self._ytdlp_version(path)
        self.ytdlp_version.emit(version)

        if self.auto_update:
            self.status.emit("Suche yt-dlp-Updates")
            try:
                if pu.ytdlp_is_bundle():
                    updated = self._update_bundle(version)
                else:
                    updated = self._update_selfupdate(path)
                if updated:
                    self.ytdlp_version.emit(self._ytdlp_version(path))
            except SetupError as exc:
                self.warning.emit(f"yt-dlp-Update übersprungen: {exc}")
        return path

    def _ytdlp_version(self, path: Path) -> str:
        res = run_binary(path, ["--version"], timeout=180)
        if res.returncode != 0:
            raise SetupError(f"yt-dlp startet nicht:\n{(res.stderr or res.stdout).strip()[:500]}",
                             gatekeeper=pu.IS_MAC)
        return res.stdout.strip()

    def _install_ytdlp(self) -> None:
        asset = pu.ytdlp_asset_name()
        self.status.emit("Lade yt-dlp herunter")
        data, _ = http_get(pu.ytdlp_download_url(), self._progress_cb("Lade yt-dlp"), timeout=60)
        self._verify_ytdlp_sha(asset, data)
        if not pu.ytdlp_is_bundle():
            _atomic_write(pu.ytdlp_path(), data)
            return
        # Zip-Bundle in temporären Ordner entpacken und dann atomar austauschen
        self.status.emit("Entpacke yt-dlp")
        target = pu.ytdlp_path().parent
        staging = Path(tempfile.mkdtemp(prefix=".yt-dlp-new-", dir=str(pu.bin_dir())))
        try:
            zpath = staging / asset
            zpath.write_bytes(data)
            out = staging / "x"
            if pu.IS_MAC:  # ditto erhält Rechte und Symlinks
                res = subprocess.run(["ditto", "-x", "-k", str(zpath), str(out)], capture_output=True, text=True)
                if res.returncode != 0:
                    raise SetupError(f"Entpacken fehlgeschlagen: {res.stderr.strip()}")
            else:
                with zipfile.ZipFile(zpath) as zf:
                    zf.extractall(out)
            exe = next(out.rglob(pu.ytdlp_path().name), None)
            if exe is None:
                raise SetupError("yt-dlp nicht im Archiv gefunden.")
            old = None
            if target.exists():
                old = pu.bin_dir() / f".yt-dlp-old-{os.getpid()}"
                shutil.rmtree(old, ignore_errors=True)
                os.replace(target, old)
            os.replace(exe.parent, target)
            if old:
                shutil.rmtree(old, ignore_errors=True)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _verify_ytdlp_sha(self, asset: str, data: bytes) -> None:
        self.status.emit("Prüfe Prüfsumme")
        try:
            sums, _ = http_get(pu.YTDLP_SHA_URL, timeout=30)
        except SetupError:
            self.warning.emit("Prüfsummen von yt-dlp nicht abrufbar – Download ungeprüft.")
            return
        for line in sums.decode("utf-8", "replace").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].lstrip("*") == asset:
                if parts[0].lower() != hashlib.sha256(data).hexdigest():
                    raise SetupError("Prüfsumme von yt-dlp stimmt nicht – Download verworfen.")
                return

    def _update_bundle(self, current: str) -> bool:
        latest = latest_ytdlp_tag()
        if not latest or _vtuple(latest) <= _vtuple(current):
            return False
        self.status.emit(f"Aktualisiere yt-dlp {current} → {latest}")
        self._install_ytdlp()
        pu.prepare_binary(pu.ytdlp_path(), pu.ytdlp_path().parent)
        return True

    def _update_selfupdate(self, path: Path) -> bool:
        upd = run_binary(path, ["-U"], timeout=180)
        out = upd.stdout + upd.stderr
        if upd.returncode != 0 and "up to date" not in out.lower():
            raise SetupError(out.strip()[-400:] or "unbekannter Fehler")
        pu.prepare_binary(path)
        return "updated yt-dlp" in out.lower()

    # ------------------------------------------------------------------ ffmpeg
    def ensure_ffmpeg(self) -> Path:
        if self.refresh_ffmpeg and not pu.find_system_ffmpeg():
            self.status.emit("Entferne alte ffmpeg-Version")
            self.remove_local_ffmpeg()
        system = pu.find_system_ffmpeg()
        if system:
            self.status.emit(f"ffmpeg gefunden: {system}")
            return system

        local = pu.ffmpeg_local_dir()
        names = ["ffmpeg" + pu.exe_suffix(), "ffprobe" + pu.exe_suffix()]
        marker = local / ".source"
        final_dir = local
        if all((local / n).is_file() for n in names):
            if self.check_ffmpeg and self._ffmpeg_outdated(marker):
                # neue Version erst in einen Nebenordner laden – die alte bleibt bis zum Erfolg erhalten
                self.status.emit("Neue ffmpeg-Version gefunden – aktualisiere")
                local = pu.bin_dir() / ".ffmpeg-new"
                shutil.rmtree(local, ignore_errors=True)
                local.mkdir(parents=True)
                marker = local / ".source"
            else:
                for n in names:
                    pu.prepare_binary(local / n)
                self._verify_ffmpeg(local / names[0])
                return local

        src = pu.ffmpeg_sources()
        if src["kind"] == "zip-per-tool":
            for tool, url in src["urls"].items():
                data, final_url = http_get(url, self._progress_cb(f"Lade {tool}"), timeout=60)
                if src.get("sha256"):
                    self._verify_sha256(data, final_url + ".sha256")
                self._extract_member(data, "zip", tool + pu.exe_suffix(), local)
        else:
            url = src["url"]
            data, _ = http_get(url, self._progress_cb("Lade ffmpeg"), timeout=60)
            kind = "zip" if url.endswith(".zip") else "tar"
            for n in names:
                self._extract_member(data, kind, n, local)

        for n in names:
            pu.prepare_binary(local / n)
        self._verify_ffmpeg(local / names[0])
        try:
            marker.write_text(ffmpeg_remote_id(), encoding="utf-8")
        except (OSError, SetupError):
            pass
        if local != final_dir:  # Update erfolgreich → alte Version ersetzen
            shutil.rmtree(final_dir, ignore_errors=True)
            os.replace(local, final_dir)
            local = final_dir
        return local

    def _ffmpeg_outdated(self, marker: Path) -> bool:
        """Vergleicht die Kennung der installierten mit der aktuell angebotenen Version."""
        self.status.emit("Suche ffmpeg-Updates")
        try:
            remote = ffmpeg_remote_id()
        except SetupError as exc:
            self.warning.emit(f"ffmpeg-Update-Prüfung übersprungen: {exc}")
            return False
        finally:
            self.ffmpeg_checked.emit()
        if not remote:
            return False
        if not marker.exists():
            # ältere Installation ohne Kennung: aktuellen Stand übernehmen statt neu zu laden
            marker.write_text(remote, encoding="utf-8")
            return False
        return marker.read_text(encoding="utf-8").strip() != remote

    def _verify_sha256(self, data: bytes, sha_url: str) -> None:
        self.status.emit("Prüfe Prüfsumme")
        sha_raw, _ = http_get(sha_url, timeout=30)
        expected = sha_raw.decode("utf-8", "replace").split()[0].strip().lower()
        actual = hashlib.sha256(data).hexdigest()
        if expected != actual:
            raise SetupError("Prüfsumme des ffmpeg-Downloads stimmt nicht – Download verworfen.")

    def _extract_member(self, data: bytes, kind: str, name: str, target_dir: Path) -> None:
        self.status.emit(f"Entpacke {name}")
        target = target_dir / name
        if kind == "zip":
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                member = next((m for m in zf.namelist() if Path(m).name == name and not m.endswith("/")), None)
                if not member:
                    raise SetupError(f"{name} nicht im Archiv gefunden.")
                _atomic_write(target, zf.read(member))
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
                member = next((m for m in tf.getmembers() if m.isfile() and Path(m.name).name == name), None)
                if not member:
                    raise SetupError(f"{name} nicht im Archiv gefunden.")
                fh = tf.extractfile(member)
                _atomic_write(target, fh.read())

    def _verify_ffmpeg(self, path: Path) -> None:
        res = run_binary(path, ["-version"], timeout=60)
        if res.returncode != 0:
            raise SetupError(f"ffmpeg startet nicht: {res.stderr.strip()[:300]}", gatekeeper=pu.IS_MAC)

    @staticmethod
    def remove_local_ffmpeg() -> None:
        shutil.rmtree(pu.ffmpeg_local_dir(), ignore_errors=True)
