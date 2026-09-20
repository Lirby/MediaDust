"""Serien-Erkennung für Playlists/Mediatheken: Staffel/Folge, Fassungen, Extras, Dateinamen.

Viele Mediatheken (ARD, Arte …) liefern Staffel/Folge nur im Titel, z. B.
„Folge 3 · Staffel 1 | Babylon Berlin (S01/E03)“ oder „Twin Peaks - Staffel 1 (3/8)“.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

_SXE = re.compile(r"\bS(\d{1,4})\s*[/|·.\-]?\s*E(\d{1,4})\b", re.IGNORECASE)
_SEASON = re.compile(r"\b(?:Staffel|Season|Saison|Temporada)\s*(\d{1,4})\b", re.IGNORECASE)
_EPISODE = re.compile(r"\b(?:Folge|Episode|Ep\.?|Teil|Part)\s*(\d{1,4})\b", re.IGNORECASE)
_FRACTION = re.compile(r"\((\d{1,4})\s*/\s*\d{1,4}\)")

# Zusatzfassungen derselben Folge (werden standardmäßig ausgeblendet)
_VARIANT = re.compile(
    r"Audiodeskription|Gebärdensprache|\bDGS\b|Hörfassung|Klare Sprache|Leichte Sprache|"
    r"Originalversion|\(OV\)|\bOmU\b|mit Untertiteln|\(AD\)", re.IGNORECASE)
_EXTRA = re.compile(
    r"\bExtras?\b|Making[- ]?of|Trailer|Teaser|Vorschau|Hinter den Kulissen|Behind the Scenes|Interview|"
    r"Featurette|Bonus|Outtakes|Podcast|Hörspiel|ARD Sounds", re.IGNORECASE)


def parse_episode(title: str, season: Optional[int] = None,
                  episode: Optional[int] = None) -> Tuple[Optional[int], Optional[int]]:
    """Ermittelt (Staffel, Folge) aus Metadaten oder – falls leer – aus dem Titel."""
    t = title or ""
    if season is None or episode is None:
        m = _SXE.search(t)
        if m:
            season = season if season is not None else int(m.group(1))
            episode = episode if episode is not None else int(m.group(2))
    if season is None:
        m = _SEASON.search(t)
        if m:
            season = int(m.group(1))
    if episode is None:
        m = _EPISODE.search(t) or (_FRACTION.search(t) if season is not None else None)
        if m:
            episode = int(m.group(1))
    return season, episode


def is_variant(title: str) -> bool:
    return bool(_VARIANT.search(title or ""))


def is_extra(title: str) -> bool:
    return bool(_EXTRA.search(title or ""))


def clean_episode_title(title: str, series: str) -> str:
    """Entfernt Serienname, SxxExx- und Staffel/Folge-Angaben aus dem Folgentitel."""
    t = title or ""
    t = _SXE.sub("", t)
    t = re.sub(r"\(\s*/?\s*\)", "", t)
    t = _FRACTION.sub("", t)
    t = _SEASON.sub("", t)
    t = _EPISODE.sub("", t)
    if series:
        t = re.sub(re.escape(series), "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*[|·:\-–]\s*(?=[|·:\-–]|$)", " ", t)   # verwaiste Trenner
    t = re.sub(r"^[\s|·:\-–]+|[\s|·:\-–]+$", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    m = re.fullmatch(r"\((.*)\)", t)
    return (m.group(1) if m else t).strip()


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str, limit: int = 150) -> str:
    name = _BAD_CHARS.sub("-", name).strip(" .")
    name = re.sub(r"-{2,}", "-", name)
    return name[:limit].rstrip(" .") or "Unbenannt"


def _is_year(season: Optional[int]) -> bool:
    return season is not None and season >= 1900


def season_folder(season: Optional[int]) -> str:
    if season is None:
        return "Weitere Folgen"
    return str(season) if _is_year(season) else f"Staffel {season:02d}"


def episode_filename(series: str, season: Optional[int], episode: Optional[int], title: str) -> str:
    """„Serie – S01E03 – Titel“ (ohne Endung)."""
    code = ""
    if _is_year(season) and episode is not None:
        code = f"{season} E{episode:02d}"
    elif season is not None and episode is not None:
        code = f"S{season:02d}E{episode:02d}"
    elif episode is not None:
        code = f"E{episode:02d}"
    clean = clean_episode_title(title, series)
    parts = [p for p in (series, code, clean or (f"Folge {episode}" if episode is not None else title)) if p]
    return safe_name(" – ".join(parts))
