"""Plattformabhängige Helfer: Pfade, Binary-Namen, Dateimanager, Autostart, natives Blur.

Alle Pfade laufen über pathlib – keine hartcodierten Windows-/Unix-Pfade.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

APP_NAME = "MediaDust"
APP_DIR_NAME = "MediaDust"  # Ordnername unter Application Support / AppData / ~/.local/share
APP_ID = "com.mediadust.app"

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")


# --------------------------------------------------------------------------- Pfade

def data_dir() -> Path:
    if IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    elif IS_WIN:
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    path = base / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def bin_dir() -> Path:
    path = data_dir() / "bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_download_dir() -> Path:
    return Path.home() / "Downloads" / APP_NAME


def resource_path(relative: str) -> Path:
    """Pfad zu gebündelten Ressourcen – funktioniert im Quellbaum und im PyInstaller-Bundle."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def exe_suffix() -> str:
    return ".exe" if IS_WIN else ""


def machine() -> str:
    m = platform.machine().lower()
    if m in ("arm64", "aarch64"):
        return "arm64"
    return "amd64"


# --------------------------------------------------------------------------- yt-dlp

YTDLP_RELEASE_BASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"


def ytdlp_asset_name() -> str:
    if IS_MAC:
        # Onedir-Variante: startet in <1 s. Die Onefile-Variante (yt-dlp_macos) entpackt sich bei
        # jedem Aufruf neu und wird dabei jedes Mal von macOS geprüft (teils >40 s pro Start).
        return "yt-dlp_macos.zip"
    if IS_WIN:
        return "yt-dlp.exe"
    return "yt-dlp_linux_aarch64" if machine() == "arm64" else "yt-dlp_linux"


def ytdlp_is_bundle() -> bool:
    """True, wenn yt-dlp als entpackter Ordner (Zip) installiert wird – dann eigenes Update statt -U."""
    return ytdlp_asset_name().endswith(".zip")


def ytdlp_path() -> Path:
    if IS_MAC:
        return bin_dir() / "yt-dlp_macos" / "yt-dlp_macos"
    return bin_dir() / ("yt-dlp" + exe_suffix())


def ytdlp_download_url() -> str:
    return YTDLP_RELEASE_BASE + ytdlp_asset_name()


YTDLP_SHA_URL = YTDLP_RELEASE_BASE + "SHA2-256SUMS"
YTDLP_LATEST_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest"


# --------------------------------------------------------------------------- ffmpeg

def ffmpeg_local_dir() -> Path:
    path = bin_dir() / "ffmpeg"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _extra_search_dirs() -> list:
    # GUI-Apps auf macOS erben nicht den PATH der Shell → Homebrew/MacPorts explizit prüfen.
    if IS_MAC:
        return [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path("/opt/local/bin")]
    if IS_LINUX:
        return [Path("/usr/bin"), Path("/usr/local/bin"), Path("/snap/bin")]
    return []


def find_system_ffmpeg() -> Optional[Path]:
    """Sucht ein vorhandenes ffmpeg (+ ffprobe im selben Ordner). Gibt den Ordner zurück."""
    name, probe = "ffmpeg" + exe_suffix(), "ffprobe" + exe_suffix()
    candidates = []
    found = shutil.which(name)
    if found:
        candidates.append(Path(found).resolve().parent)
        candidates.append(Path(found).parent)
    candidates += _extra_search_dirs()
    for d in candidates:
        if (d / name).is_file() and (d / probe).is_file() and os.access(d / name, os.X_OK):
            return d
    return None


def ffmpeg_sources() -> dict:
    """Download-Quellen je Plattform. Rückgabe: {"kind": ..., ...}."""
    if IS_MAC:
        base = f"https://ffmpeg.martin-riedl.de/redirect/latest/macos/{machine()}/release/"
        return {"kind": "zip-per-tool", "urls": {"ffmpeg": base + "ffmpeg.zip", "ffprobe": base + "ffprobe.zip"},
                "sha256": True}
    if IS_WIN:
        return {"kind": "archive",
                "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
                       "ffmpeg-master-latest-win64-gpl.zip"}
    arch = "linuxarm64" if machine() == "arm64" else "linux64"
    return {"kind": "archive",
            "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
                   f"ffmpeg-master-latest-{arch}-gpl.tar.xz"}


# --------------------------------------------------------------------------- Binaries vorbereiten

def prepare_binary(path: Path, recursive_dir: Optional[Path] = None) -> None:
    """chmod +x und (macOS) Quarantäne-Attribut entfernen, damit Gatekeeper nicht blockiert."""
    if IS_WIN:
        return
    mode = path.stat().st_mode
    path.chmod(mode | 0o755)
    if IS_MAC:
        target = recursive_dir or path
        args = ["xattr", "-dr" if recursive_dir else "-d", "com.apple.quarantine", str(target)]
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def gatekeeper_hint(path: Path) -> str:
    if not IS_MAC:
        return f"Die Datei {path} konnte nicht ausgeführt werden. Bitte Berechtigungen prüfen."
    return (
        f"macOS hat die Ausführung von „{path.name}“ blockiert (Gatekeeper).\n\n"
        "Lösung: Systemeinstellungen → Datenschutz & Sicherheit → bei der Meldung zu "
        f"„{path.name}“ auf „Trotzdem erlauben“ klicken – oder im Terminal ausführen:\n\n"
        f"xattr -d com.apple.quarantine \"{path}\"\nchmod +x \"{path}\""
    )


def subprocess_kwargs() -> dict:
    """Plattformgerechte Popen-Argumente: eigene Prozessgruppe, kein Konsolenfenster."""
    if IS_WIN:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return {"creationflags": flags}
    return {"start_new_session": True}


def kill_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    except Exception:
        try:
            if not IS_WIN:
                import signal
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            else:
                proc.kill()
        except Exception:
            pass


# --------------------------------------------------------------------------- Dateimanager

def file_manager_name() -> str:
    if IS_MAC:
        return "Im Finder anzeigen"
    if IS_WIN:
        return "Im Explorer anzeigen"
    return "Im Dateimanager anzeigen"


def reveal_in_file_manager(path: Path) -> None:
    path = Path(path)
    if IS_MAC:
        if path.exists():
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["open", str(path.parent)])
    elif IS_WIN:
        if path.exists():
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            os.startfile(str(path.parent))  # type: ignore[attr-defined]
    else:
        target = path if path.is_dir() else path.parent
        subprocess.Popen(["xdg-open", str(target)])


def open_path(path: Path) -> None:
    if IS_MAC:
        subprocess.Popen(["open", str(path)])
    elif IS_WIN:
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])


# --------------------------------------------------------------------------- Autostart

def _launch_command() -> list:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return [str(exe)]
    return [sys.executable, str(Path(__file__).resolve().parent / "main.py")]


def set_autostart(enabled: bool) -> None:
    cmd = _launch_command()
    if IS_MAC:
        plist = Path.home() / "Library" / "LaunchAgents" / f"{APP_ID}.plist"
        if enabled:
            import plistlib
            plist.parent.mkdir(parents=True, exist_ok=True)
            with plist.open("wb") as fh:
                plistlib.dump({"Label": APP_ID, "ProgramArguments": cmd,
                               "RunAtLoad": True, "ProcessType": "Interactive"}, fh)
        elif plist.exists():
            plist.unlink()
    elif IS_WIN:
        import winreg  # type: ignore
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        try:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
    else:
        desktop = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "autostart" / "mediadust.desktop"
        if enabled:
            desktop.parent.mkdir(parents=True, exist_ok=True)
            import shlex
            desktop.write_text(
                "[Desktop Entry]\nType=Application\nName=MediaDust\n"
                f"Exec={' '.join(shlex.quote(c) for c in cmd)}\nX-GNOME-Autostart-enabled=true\n",
                encoding="utf-8")
        elif desktop.exists():
            desktop.unlink()


# --------------------------------------------------------------------------- Natives Blur

def apply_native_blur(widget, radius: float = 14.0, style: str = "blur") -> bool:
    """Versucht natives Blur hinter dem Fenster zu aktivieren. False → QSS-Fallback verwenden."""
    try:
        if IS_MAC:
            return _mac_vibrancy(widget, radius, style)
        if IS_WIN:
            return False  # TODO: DWM Acrylic (SetWindowCompositionAttribute) – später
    except Exception as exc:  # jeglicher Fehler → Fallback
        print(f"[MediaDust] Natives Blur nicht verfügbar: {exc}", file=sys.stderr)
    return False


def _mac_vibrancy(widget, radius: float, style: str = "blur") -> bool:
    """style="blur": NSVisualEffectView (starkes, dunkles Blur).
    style="liquid": Liquid Glass (NSGlassEffectView, macOS 26+), sonst Rückfall auf "blur"."""
    import objc  # type: ignore
    from AppKit import (NSAppearance, NSVisualEffectView, NSViewWidthSizable,  # type: ignore
                        NSViewHeightSizable, NSWindowBelow, NSColor)

    view = objc.objc_object(c_void_p=int(widget.winId()))
    window = view.window()
    if window is None:
        return False
    content = window.contentView()
    frame_view = content.superview()
    if frame_view is None:
        return False

    effect = None
    glass_cls = None
    if style == "liquid":
        try:
            glass_cls = objc.lookUpClass("NSGlassEffectView")
        except objc.error:
            glass_cls = None
    if glass_cls is not None:
        effect = glass_cls.alloc().initWithFrame_(content.frame())
        effect.setCornerRadius_(radius)
        if effect.respondsToSelector_(b"setStyle:"):
            effect.setStyle_(0)  # NSGlassEffectViewStyleRegular (gut lesbar)
        # dunkles Lila als Glastönung
        effect.setTintColor_(NSColor.colorWithSRGBRed_green_blue_alpha_(0.07, 0.02, 0.17, 0.78))
    else:
        effect = NSVisualEffectView.alloc().initWithFrame_(content.frame())
        effect.setBlendingMode_(0)   # BehindWindow
        effect.setMaterial_(13)      # HUDWindow: kräftiges, dunkles Blur
        effect.setState_(1)          # Active (auch wenn das Fenster nicht im Fokus ist)
        effect.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
        effect.setWantsLayer_(True)
        effect.layer().setCornerRadius_(radius)
        effect.layer().setMasksToBounds_(True)
    effect.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    frame_view.addSubview_positioned_relativeTo_(effect, NSWindowBelow, content)

    window.setOpaque_(False)
    window.setBackgroundColor_(NSColor.clearColor())
    window.setHasShadow_(True)
    widget._native_blur_view = effect  # Referenz halten
    widget._native_frame_view = frame_view
    # Alles auf die abgerundete Form beschneiden – sonst bleiben an den Ecken schwarze Reste stehen
    set_native_corner_radius(widget, radius)
    return True


def set_native_corner_radius(widget, radius: float) -> None:
    """Passt die Eckenrundung der nativen Glasfläche an (z. B. 0 im maximierten Zustand)."""
    if not IS_MAC:
        return
    effect = getattr(widget, "_native_blur_view", None)
    frame_view = getattr(widget, "_native_frame_view", None)
    if effect is None or frame_view is None:
        return
    try:
        if effect.respondsToSelector_(b"setCornerRadius:"):
            effect.setCornerRadius_(radius)
        for v in (frame_view, frame_view.window().contentView()):
            v.setWantsLayer_(True)
            layer = v.layer()
            layer.setCornerRadius_(radius)
            layer.setMasksToBounds_(True)
        if not effect.respondsToSelector_(b"setCornerRadius:"):
            effect.layer().setCornerRadius_(radius)
        frame_view.window().invalidateShadow()
    except Exception as exc:
        print(f"[MediaDust] Eckenrundung nicht gesetzt: {exc}", file=sys.stderr)
