# Third-Party Notices

MediaDust is licensed under the GNU General Public License v3.0 (see `LICENSE`).
It uses the following third-party software.

## Bundled in the app

| Component | License | Source |
|---|---|---|
| Qt for Python (PySide6, Shiboken6) and Qt | LGPL-3.0 (see `licenses/LGPL-3.0.txt`) | https://code.qt.io/cgit/pyside/pyside-setup.git |
| Python | PSF License | https://www.python.org |
| certifi | MPL-2.0 | https://github.com/certifi/python-certifi |
| PyObjC (macOS only) | MIT | https://github.com/ronaldoussoren/pyobjc |
| PyInstaller bootloader | GPL-2.0 with bootloader exception | https://github.com/pyinstaller/pyinstaller |

Qt and PySide6 are shipped as separate, dynamically loaded libraries inside the app bundle
(`MediaDust.app/Contents/Frameworks`). You may replace them with your own compatible build.
The corresponding source code is available at the links above.

## Downloaded on first launch (not bundled)

| Component | License | Source |
|---|---|---|
| yt-dlp | Unlicense | https://github.com/yt-dlp/yt-dlp |
| ffmpeg / ffprobe | LGPL-2.1+ / GPL-2.0+ (depending on the build) | https://ffmpeg.org |
