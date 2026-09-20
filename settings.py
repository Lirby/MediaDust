"""Einstellungen laden/speichern (JSON im plattformabhängigen Datenordner)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields

from platform_utils import data_dir, default_download_dir

VIDEO_QUALITIES = [("best", "Beste"), ("4320", "4320p (8K)"), ("2160", "2160p (4K)"), ("1440", "1440p (2K)"),
                   ("1080", "1080p (Full HD)"), ("720", "720p (HD)"), ("480", "480p"), ("360", "360p"),
                   ("240", "240p"), ("144", "144p")]
AUDIO_BITRATES = [("320", "320 kbit/s"), ("256", "256 kbit/s"), ("192", "192 kbit/s"),
                  ("128", "128 kbit/s"), ("96", "96 kbit/s")]
VIDEO_FORMATS = [("mp4", "MP4"), ("mkv", "MKV"), ("webm", "WebM"), ("mov", "MOV")]
AUDIO_FORMATS = [("mp3", "MP3"), ("m4a", "M4A (AAC)"), ("opus", "Opus"), ("ogg", "OGG (Vorbis)"),
                 ("flac", "FLAC (verlustfrei)"), ("wav", "WAV (unkomprimiert)"), ("best", "Original")]
LOSSLESS_AUDIO = {"flac", "wav", "best"}
AFTER_COMPLETE = [("nothing", "Nichts tun"), ("notify", "Benachrichtigung anzeigen"),
                  ("open_folder", "Zielordner öffnen"), ("quit", "MediaDust beenden")]


@dataclass
class Settings:
    download_dir: str = str(default_download_dir())
    max_parallel_video: int = 3
    max_parallel_audio: int = 5
    default_mode: str = "video"          # "video" | "audio"
    default_quality: str = "1080"
    default_audio_bitrate: str = "192"
    default_video_format: str = "mp4"
    default_audio_format: str = "mp3"
    autostart: bool = False
    after_complete: str = "notify"       # gilt, wenn die komplette Queue fertig ist
    native_blur: bool = True
    auto_update: bool = True
    ffmpeg_auto_update: bool = True    # wöchentlich prüfen
    ffmpeg_last_check: float = 0.0
    autostart_downloads: bool = True
    playlist_confirm_threshold: int = 25

    @property
    def path(self):
        return data_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        try:
            raw = json.loads(s.path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            for key, value in raw.items():
                if key in known:
                    setattr(s, key, value)
        except (OSError, ValueError):
            pass
        s.max_parallel_video = max(1, min(10, int(s.max_parallel_video)))
        s.max_parallel_audio = max(1, min(10, int(s.max_parallel_audio)))
        return s

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
