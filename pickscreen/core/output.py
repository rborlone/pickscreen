"""Salida de una captura: portapapeles y archivo."""
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf

from . import config


def copy_pixbuf(pixbuf, display=None) -> None:
    """Copia la imagen al portapapeles.

    Se usa el portapapeles de GTK (sirve en Wayland y X11). Si existe `wl-copy`,
    se usa además porque deja la imagen disponible aunque la app se cierre
    (en GNOME/Wayland el portapapeles se pierde al cerrar quien lo puso).
    """
    display = display or Gdk.Display.get_default()
    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
    display.get_clipboard().set_content(Gdk.ContentProvider.new_for_value(texture))

    if shutil.which("wl-copy"):
        ok, data = pixbuf.save_to_bufferv("png", [], [])
        if ok:
            subprocess.Popen(
                ["wl-copy", "--type", "image/png"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).communicate(data)


def copy_text(text: str, display=None) -> None:
    """Copia texto al portapapeles (y con `wl-copy` si existe, para que persista)."""
    display = display or Gdk.Display.get_default()
    display.get_clipboard().set_content(Gdk.ContentProvider.new_for_value(text))
    if shutil.which("wl-copy"):
        subprocess.Popen(
            ["wl-copy"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).communicate(text.encode())


def _flatten(pixbuf):
    """JPG no admite transparencia: componer la imagen sobre fondo blanco."""
    if not pixbuf.get_has_alpha():
        return pixbuf
    w, h = pixbuf.get_width(), pixbuf.get_height()
    flat = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, w, h)
    flat.fill(0xFFFFFFFF)
    pixbuf.composite(flat, 0, 0, w, h, 0, 0, 1, 1, GdkPixbuf.InterpType.NEAREST, 255)
    return flat


def save_pixbuf(pixbuf, cfg: dict, path: Path | None = None) -> Path:
    """Guarda la imagen y devuelve la ruta.

    Sin `path`, crea un archivo nuevo con nombre por fecha/hora. Con `path`,
    sobrescribe ese archivo (así una captura editada no se guarda dos veces).
    """
    if path is None:
        folder = config.save_dir(cfg)
        folder.mkdir(parents=True, exist_ok=True)
        ext = "jpg" if cfg.get("format") == "jpg" else "png"
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = folder / f"pickscreen_{stamp}.{ext}"
        n = 1
        while path.exists():  # dos capturas en el mismo segundo
            path = folder / f"pickscreen_{stamp}_{n}.{ext}"
            n += 1
    path = Path(path)
    ext = "jpg" if path.suffix.lower() in (".jpg", ".jpeg") else "png"

    if ext == "jpg":
        quality = str(cfg.get("jpg_quality", 92))
        _flatten(pixbuf).savev(str(path), "jpeg", ["quality"], [quality])
    else:
        pixbuf.savev(str(path), "png", [], [])
    return path
