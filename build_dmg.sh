#!/usr/bin/env bash
# Baut dist/MediaDust-<Version>-arm64.dmg (Apple Silicon, ad-hoc signiert).
#
#   ./build_dmg.sh
#
# Legt bei Bedarf ein .venv mit Homebrew-Python 3.12 an, baut die App mit PyInstaller
# (build.spec) und packt sie mit Programme-Verknüpfung und Hintergrund (dmg_settings.py) in eine DMG.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

APP_NAME="MediaDust"
PYTHON="${PYTHON:-/opt/homebrew/bin/python3.12}"
VENV="$ROOT/.venv"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' main.py)"
ARCH="$(uname -m)"
DMG="$ROOT/dist/$APP_NAME-$VERSION-$ARCH.dmg"

[[ "$(uname)" == "Darwin" ]] || { echo "Nur auf macOS lauffähig." >&2; exit 1; }
[[ -n "$VERSION" ]] || { echo "VERSION in main.py nicht gefunden." >&2; exit 1; }

# --- Build-Umgebung
if [[ ! -x "$VENV/bin/python" ]]; then
    echo "→ Lege .venv an ($PYTHON)"
    "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r requirements.txt

# --- Icon (assets/ ist in .gitignore)
if [[ ! -f assets/icon.icns ]]; then
    echo "→ Erzeuge Icon"
    if [[ -f assets/icon.png ]]; then
        "$VENV/bin/python" tools/png_to_icns.py
    else
        "$VENV/bin/python" tools/make_icon.py
    fi
fi

# --- App bauen
echo "→ Baue $APP_NAME.app $VERSION ($ARCH)"
rm -rf build "dist/$APP_NAME" "dist/$APP_NAME.app"
"$VENV/bin/pyinstaller" --noconfirm --clean --log-level WARN build.spec

APP="dist/$APP_NAME.app"
# Gesamtes Bundle ad-hoc signieren (sonst meldet macOS die App als „beschädigt“)
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

# --- DMG (lila Milchglas-Hintergrund, App → Programme)
echo "→ Erzeuge DMG"
if [[ ! -f assets/dmg_background.tiff || tools/make_dmg_background.py -nt assets/dmg_background.tiff ]]; then
    QT_QPA_PLATFORM=offscreen "$VENV/bin/python" tools/make_dmg_background.py
fi
rm -f "$DMG"
"$VENV/bin/dmgbuild" -s dmg_settings.py -D app="$APP" "$APP_NAME $VERSION" "$DMG"
hdiutil verify -quiet "$DMG"

echo "✓ Fertig: $DMG ($(du -h "$DMG" | cut -f1))"
