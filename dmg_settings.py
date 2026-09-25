# dmgbuild-Einstellungen für build_dmg.sh (Fensterlayout passend zu tools/make_dmg_background.py).
# Aufruf: dmgbuild -s dmg_settings.py -D app=dist/MediaDust.app "MediaDust" dist/MediaDust.dmg
import os.path

app = defines["app"]  # noqa: F821 – von dmgbuild bereitgestellt
app_name = os.path.basename(app)

format = "UDZO"
compression_level = 9
filesystem = "HFS+"

files = [app]
symlinks = {"Programme": "/Applications"}

background = os.path.join(os.path.dirname(os.path.abspath(app)), "..", "assets", "dmg_background.tiff")
window_rect = ((200, 120), (640, 400))
default_view = "icon-view"
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False

icon_size = 128
text_size = 13
icon_locations = {
    app_name: (160, 180),
    "Programme": (480, 180),
}
