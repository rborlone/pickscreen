"""Reconocimiento de texto (OCR) con Tesseract."""
import shutil
import subprocess
import threading

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib
from .i18n import _

PREFERRED_LANGS = ["spa", "eng"]
_langs_cache = None


class OcrError(Exception):
    pass


def available() -> bool:
    return shutil.which("tesseract") is not None


def install_hint() -> str:
    return (_("Tesseract no está instalado. Instálalo con:") + "\n"
            "  Fedora: sudo dnf install tesseract tesseract-langpack-spa\n"
            "  Debian/Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-spa\n"
            "  Arch: sudo pacman -S tesseract tesseract-data-spa tesseract-data-eng")


def installed_languages() -> list:
    global _langs_cache
    if _langs_cache is None:
        try:
            out = subprocess.run(["tesseract", "--list-langs"], capture_output=True,
                                 text=True, timeout=15).stdout
            _langs_cache = [l.strip() for l in out.splitlines()[1:] if l.strip()]
        except (OSError, subprocess.SubprocessError):
            _langs_cache = []
    return _langs_cache


def pick_languages(preferred=None) -> str:
    """Español + inglés si están; si no, lo que haya instalado."""
    have = installed_languages()
    chosen = [l for l in (preferred or PREFERRED_LANGS) if l in have]
    if not chosen:
        chosen = ["eng"] if "eng" in have else [l for l in have if l != "osd"][:1]
    if not chosen:
        raise OcrError(_("Tesseract no tiene ningún idioma instalado."))
    return "+".join(chosen)


def _prepare(pixbuf):
    """Tesseract lee mejor el texto pequeño de pantalla si se amplía."""
    w, h = pixbuf.get_width(), pixbuf.get_height()
    if max(w, h) <= 2000:
        return pixbuf.scale_simple(w * 2, h * 2, GdkPixbuf.InterpType.BILINEAR)
    return pixbuf


def recognize(pixbuf, psm=None, preferred_langs=None) -> str:
    """Devuelve el texto de la imagen. `psm=6` va bien para un bloque de texto."""
    if not available():
        raise OcrError(install_hint())
    ok, data = _prepare(pixbuf).save_to_bufferv("png", [], [])
    if not ok:
        raise OcrError(_("No se pudo preparar la imagen."))
    cmd = ["tesseract", "stdin", "stdout", "-l", pick_languages(preferred_langs)]
    if psm:
        cmd += ["--psm", str(psm)]
    try:
        proc = subprocess.run(cmd, input=data, capture_output=True, timeout=90)
    except subprocess.TimeoutExpired as exc:
        raise OcrError(_("El reconocimiento tardó demasiado.")) from exc
    except OSError as exc:
        raise OcrError(str(exc)) from exc
    if proc.returncode != 0:
        raise OcrError(proc.stderr.decode(errors="replace").strip() or _("Tesseract falló."))
    text = proc.stdout.decode(errors="replace").replace("\x0c", "")
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def recognize_async(pixbuf, callback, psm=None, preferred_langs=None) -> None:
    """Reconoce en un hilo para no congelar la ventana. `callback(texto, error)` corre en el hilo principal."""
    def work():
        try:
            result = (recognize(pixbuf, psm, preferred_langs), None)
        except OcrError as exc:
            result = (None, str(exc))
        GLib.idle_add(lambda: callback(*result) and False)

    threading.Thread(target=work, daemon=True).start()
