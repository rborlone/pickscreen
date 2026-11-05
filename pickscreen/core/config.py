"""Preferencias de pickscreen (JSON en el directorio de configuración XDG)."""
import json
from pathlib import Path

from gi.repository import GLib

DEFAULTS = {
    "auto_copy": True,      # copiar al portapapeles tras capturar/editar
    "auto_save": True,      # guardar archivo tras capturar/editar
    "format": "png",        # "png" o "jpg"
    "jpg_quality": 92,
    "save_dir": None,       # None -> <Imágenes>/Screenshots
    "ocr_langs": None,      # None -> español + inglés; o p. ej. ["spa"]
    "video_dir": None,      # None -> <Vídeos>/Screencasts
    "video_audio": False,   # grabar también el micrófono
    "video_fps": 30,
    "language": None,       # None -> idioma del sistema; o "es" / "en" (se aplica al reiniciar)
    "tray": True,           # ícono en la barra superior (servicio)
    "global_shortcuts": True,   # el servicio registra atajos globales (si el escritorio lo permite)
}


def _config_file() -> Path:
    return Path(GLib.get_user_config_dir()) / "pickscreen" / "config.json"


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(_config_file().read_text()))
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg: dict) -> None:
    path = _config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))


def save_dir(cfg: dict) -> Path:
    if cfg.get("save_dir"):
        return Path(cfg["save_dir"]).expanduser()
    pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
    return Path(pictures or Path.home() / "Pictures") / "Screenshots"


def video_dir(cfg: dict) -> Path:
    if cfg.get("video_dir"):
        return Path(cfg["video_dir"]).expanduser()
    videos = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS)
    return Path(videos or Path.home() / "Videos") / "Screencasts"
