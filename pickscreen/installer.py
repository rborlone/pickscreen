"""Instalación de pickscreen en la sesión del usuario (sin root).

    pickscreen install [--no-systemctl] [--root DIR]
    pickscreen uninstall [--root DIR]
    pickscreen gnome-print on|off [--dry-run]
"""
import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_ID = "cl.pickscreen.App"
PROJECT_DIR = Path(__file__).resolve().parent.parent      # carpeta que contiene el paquete
ICON_SOURCE = Path(__file__).resolve().parent / "data" / f"{APP_ID}.svg"

HELP = """pickscreen: capturas, anotaciones y OCR

Uso:
  pickscreen [capture]      captura y abre el editor
  pickscreen ocr            elegir una zona y copiar su texto
  pickscreen record         iniciar la grabación de pantalla (o detenerla)
  pickscreen daemon         servicio en segundo plano (atajos globales)
  pickscreen quit           cierra la instancia en ejecución

Instalación (solo tu usuario, sin root):
  pickscreen install [--no-systemctl]   ícono, menú de aplicaciones, servicio
  pickscreen uninstall                  lo quita todo
  pickscreen gnome-print on|off         usar la tecla Impr Pant con pickscreen (GNOME)
"""


def _paths(root: Path) -> dict:
    return {
        "launcher": root / ".local/bin/pickscreen",
        "icon": root / ".local/share/icons/hicolor/scalable/apps" / f"{APP_ID}.svg",
        "desktop": root / ".local/share/applications" / f"{APP_ID}.desktop",
        "dbus": root / ".local/share/dbus-1/services" / f"{APP_ID}.service",
        "unit": root / ".config/systemd/user/pickscreen.service",
    }


def _contents(launcher: Path) -> dict:
    exe = str(launcher)
    return {
        "launcher": (
            "#!/bin/sh\n"
            f'PYTHONPATH="{PROJECT_DIR}${{PYTHONPATH:+:$PYTHONPATH}}" exec {sys.executable} -m pickscreen "$@"\n'
        ),
        "desktop": (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=pickscreen\n"
            "Comment=Capturar, anotar y copiar texto (OCR) de la pantalla\n"
            "Comment[en]=Capture, annotate and copy text (OCR) from the screen\n"
            f"Exec={exe} capture\n"
            f"Icon={APP_ID}\n"
            "Terminal=false\n"
            "Categories=Graphics;GTK;\n"
            "Keywords=screenshot;captura;pantalla;ocr;grabar;\n"
            "DBusActivatable=true\n"
            "StartupNotify=true\n"
            "Actions=capture;ocr;record;\n"
            "\n"
            "[Desktop Action capture]\n"
            "Name=Capturar pantalla\n"
            "Name[en]=Take screenshot\n"
            f"Exec={exe} capture\n"
            "\n"
            "[Desktop Action ocr]\n"
            "Name=Copiar texto de una zona (OCR)\n"
            "Name[en]=Copy text from an area (OCR)\n"
            f"Exec={exe} ocr\n"
            "\n"
            "[Desktop Action record]\n"
            "Name=Grabar pantalla\n"
            "Name[en]=Record screen\n"
            f"Exec={exe} record\n"
        ),
        "dbus": (
            "[D-BUS Service]\n"
            f"Name={APP_ID}\n"
            f"Exec={exe} --gapplication-service\n"
            "SystemdService=pickscreen.service\n"
        ),
        "unit": (
            "[Unit]\n"
            "Description=pickscreen (capturas, anotaciones y OCR)\n"
            "After=graphical-session.target\n"
            "PartOf=graphical-session.target\n"
            "\n"
            "[Service]\n"
            "Type=dbus\n"
            f"BusName={APP_ID}\n"
            f"ExecStart={exe} daemon\n"
            "Restart=on-failure\n"
            "\n"
            "[Install]\n"
            "WantedBy=graphical-session.target\n"
        ),
    }


def _run(cmd, check=True):
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, check=check)


def install(root: Path, use_systemctl: bool) -> int:
    paths = _paths(root)
    contents = _contents(paths["launcher"])
    for key, text in contents.items():
        paths[key].parent.mkdir(parents=True, exist_ok=True)
        paths[key].write_text(text)
    paths["launcher"].chmod(0o755)
    paths["icon"].parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ICON_SOURCE, paths["icon"])
    print("Archivos instalados:")
    for p in paths.values():
        print("  ", p)

    if use_systemctl:
        _run(["systemctl", "--user", "daemon-reload"])
        _run(["systemctl", "--user", "enable", "--now", "pickscreen.service"])
        print("Servicio activo. Estado: systemctl --user status pickscreen")
    if str(paths["launcher"].parent) not in os.environ.get("PATH", "").split(":"):
        print(f"Aviso: {paths['launcher'].parent} no está en tu PATH; "
              "el comando `pickscreen` solo funcionará con la ruta completa.")
    return 0


def uninstall(root: Path) -> int:
    paths = _paths(root)
    if root == Path.home():
        _run(["systemctl", "--user", "disable", "--now", "pickscreen.service"], check=False)
    for p in paths.values():
        if p.exists():
            p.unlink()
            print("  borrado", p)
    if root == Path.home():
        _run(["systemctl", "--user", "daemon-reload"], check=False)
    return 0


# ------------------------------------------------- Impr Pant en GNOME (reversible)
_SHELL = "org.gnome.shell.keybindings"
_MEDIA = "org.gnome.settings-daemon.plugins.media-keys"
_CUSTOM_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/pickscreen/"
_CUSTOM_SCHEMA = f"{_MEDIA}.custom-keybinding:{_CUSTOM_PATH}"


def _gs(args, dry_run, read=False):
    if read or not dry_run:
        out = subprocess.run(["gsettings", *args], capture_output=True, text=True, check=True).stdout.strip()
        if not read:
            print("  $ gsettings", " ".join(args))
        return out
    print("  [simulación] gsettings", " ".join(args))
    return ""


def _as_list(text: str) -> list:
    return ast.literal_eval(text.replace("@as ", "")) if text else []


def gnome_print(action: str, dry_run: bool) -> int:
    if not shutil.which("gsettings"):
        print("gsettings no está disponible: esta opción es solo para GNOME.")
        return 1
    backup = Path.home() / ".config/pickscreen/gnome-print-backup.json"
    custom = _as_list(_gs(["get", _MEDIA, "custom-keybindings"], dry_run, read=True))

    if action == "on":
        if not dry_run and not backup.exists():       # no pisar la copia original
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(json.dumps(
                {"show-screenshot-ui": _gs(["get", _SHELL, "show-screenshot-ui"], dry_run, read=True)}))
        _gs(["set", _SHELL, "show-screenshot-ui", "[]"], dry_run)
        if _CUSTOM_PATH not in custom:
            _gs(["set", _MEDIA, "custom-keybindings", str(custom + [_CUSTOM_PATH])], dry_run)
        _gs(["set", _CUSTOM_SCHEMA, "name", "pickscreen"], dry_run)
        _gs(["set", _CUSTOM_SCHEMA, "command", f"{_paths(Path.home())['launcher']} capture"], dry_run)
        _gs(["set", _CUSTOM_SCHEMA, "binding", "Print"], dry_run)
        print("Listo: Impr Pant abre pickscreen. Para volver al visor de GNOME: pickscreen gnome-print off")
    elif action == "off":
        saved = json.loads(backup.read_text()) if backup.exists() else {}
        _gs(["set", _SHELL, "show-screenshot-ui", saved.get("show-screenshot-ui", "['Print']")], dry_run)
        _gs(["set", _MEDIA, "custom-keybindings", str([p for p in custom if p != _CUSTOM_PATH])], dry_run)
        _gs(["reset-recursively", _CUSTOM_SCHEMA], dry_run)
        if backup.exists() and not dry_run:
            backup.unlink()
        print("Listo: Impr Pant vuelve a abrir el visor de capturas de GNOME.")
    else:
        print("Uso: pickscreen gnome-print on|off [--dry-run]")
        return 2
    return 0


def run(args: list) -> int:
    command, rest = args[0], args[1:]
    root = Path.home()
    if "--root" in rest:
        root = Path(rest[rest.index("--root") + 1]).expanduser().resolve()
    if command in ("help", "--help", "-h"):
        print(HELP)
        return 0
    if command == "install":
        return install(root, use_systemctl="--no-systemctl" not in rest and root == Path.home())
    if command == "uninstall":
        return uninstall(root)
    if command == "gnome-print":
        positional = [a for a in rest if not a.startswith("--")]
        return gnome_print(positional[0] if positional else "", "--dry-run" in rest)
    return 2
