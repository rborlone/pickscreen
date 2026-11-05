"""Aplicación: captura con el portal y editor; también hace de servicio de usuario.

Al ser una Gio.Application hay una sola instancia por sesión: si ya está
corriendo (por ejemplo como servicio), `pickscreen capture` se reenvía a ese
proceso por D-Bus. Comandos: capture (por defecto), ocr, record, daemon, quit.
"""
import subprocess
import sys
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, GdkPixbuf, Gio, GLib

from .core import capture, config, ocr, output
from .core.recorder import Recorder
from .core.tray import Tray
from .core.shortcuts import GlobalShortcuts
from .ui.editor import EditorWindow
from .ui.preferences import PreferencesDialog
from .ui.recording import RecordingWindow
from .core.i18n import _

APP_ID = "cl.pickscreen.App"


class PickScreenApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.cfg = config.load()
        self.window = None
        self.mode = "edit"          # "edit": abre el editor · "ocr": copia el texto y listo
        self._capturing = False
        self._daemon = False
        self._shortcuts = None
        self.recorder = None
        self.rec_window = None
        self.tray = None

        # Acciones accesibles por D-Bus (`gapplication action cl.pickscreen.App capture`)
        # y desde el menú de la app en el escritorio.
        for name, mode in (("capture", "edit"), ("ocr", "ocr")):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, m=mode: self.new_capture(m))
            self.add_action(action)
        record = Gio.SimpleAction.new("record", None)
        record.connect("activate", lambda *_a: self.toggle_recording())
        self.add_action(record)
        prefs = Gio.SimpleAction.new("preferences", None)
        prefs.connect("activate", lambda *_a: self.show_preferences())
        self.add_action(prefs)
        self._prefs = None

    # ------------------------------------------------------- línea de comandos
    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        command = args[0].lstrip("-") if args else "capture"
        if command == "daemon":
            self._start_daemon()
        elif command == "capture":
            self.new_capture("edit")
        elif command == "ocr":
            self.new_capture("ocr")
        elif command == "record":
            self.toggle_recording()
        elif command in ("preferences", "prefs"):
            self.show_preferences()
        elif command == "quit":
            self.quit()
        else:
            message = (f"pickscreen: comando desconocido «{args[0]}». "
                       "Usa: capture, ocr, record, preferences, daemon, quit.\n")
            getattr(cmdline, "printerr_literal", lambda m: print(m, file=sys.stderr, end=""))(message)
            return 2
        return 0

    def do_activate(self):
        self.new_capture("edit")     # activación D-Bus (p. ej. desde el menú de aplicaciones)

    # --------------------------------------------------------------- servicio
    def _start_daemon(self):
        if self._daemon:
            return
        self._daemon = True
        self.hold()                  # seguir vivo aunque se cierre el editor
        print("pickscreen: servicio iniciado", flush=True)
        self.set_tray_enabled(self.cfg.get("tray", True))
        if self.cfg.get("global_shortcuts", True):
            self._shortcuts = GlobalShortcuts(self._on_shortcut,
                                              on_status=lambda m: print(f"pickscreen: {m}", flush=True))
            self._shortcuts.start()

    def set_tray_enabled(self, enabled):
        """Muestra u oculta el ícono de la bandeja sin reiniciar el servicio."""
        if enabled and self.tray is None:
            self.tray = Tray(APP_ID, lambda: self.new_capture("edit"), lambda: self.new_capture("ocr"),
                             self.toggle_recording, self.quit, self.show_preferences)
            self.tray.start()
            self.tray.set_recording(self.recorder is not None and self.recorder.recording)
        elif not enabled and self.tray is not None:
            self.tray.stop()
            self.tray = None

    def restart(self):
        """Reinicia el servicio para aplicar cambios que se leen al arrancar (p. ej. el idioma)."""
        if self._daemon:
            subprocess.Popen(["systemctl", "--user", "restart", "pickscreen"])
        else:
            self.quit()

    def shortcut_triggers(self):
        """Teclas que el portal tiene asignadas (vacío si no hay atajos globales)."""
        return dict(self._shortcuts.triggers) if self._shortcuts else {}

    def show_preferences(self):
        if self._prefs is not None:          # ya abierta: traerla al frente
            self._prefs.present(self.window)
            return
        self._prefs = PreferencesDialog(self.cfg, self)
        self._prefs.connect("closed", lambda *_a: setattr(self, "_prefs", None))
        self._prefs.present(self.window)

    def _on_shortcut(self, shortcut_id):
        if shortcut_id == "capture":
            self.new_capture("edit")
        elif shortcut_id == "ocr":
            self.new_capture("ocr")
        elif shortcut_id == "record":
            self.toggle_recording()

    # --------------------------------------------------------------- grabación
    def toggle_recording(self):
        """Primera vez: elegir qué grabar e iniciar. Con una grabación en curso: detenerla."""
        if self.recorder is not None:
            if self.recorder.recording:
                self.recorder.stop()
            return                    # arrancando (selector abierto): no hacer nada
        self.hold()
        self.recorder = Recorder(self.cfg, self._on_rec_started, self._on_rec_finished)
        self.recorder.start()

    def _on_rec_started(self, path):
        print(f"pickscreen: grabando en {path}", flush=True)
        if self.tray:
            self.tray.set_recording(True)
        self.rec_window = RecordingWindow(self, self.toggle_recording)
        self.rec_window.present()

    def _on_rec_finished(self, path, error):
        self.recorder = None
        if self.tray:
            self.tray.set_recording(False)
        if error:
            print(f"pickscreen: {error}", file=sys.stderr, flush=True)
        if path:
            print(f"pickscreen: grabación guardada en {path}", flush=True)
        if self.rec_window:
            self.rec_window.show_done(path, error)
        elif error or path:
            self._notify(_("No se pudo grabar") if error else _("Grabación guardada"), error or str(path))
        self.release()

    # ---------------------------------------------------------------- captura
    def new_capture(self, mode="edit"):
        if self._capturing:          # ya hay un selector abierto (atajo pulsado dos veces)
            return
        self._capturing = True
        self.mode = mode
        if self.window:
            self.window.finish()      # copiar/guardar lo editado antes de seguir
            self.window.set_visible(False)
        self.hold()                   # mantener viva la app mientras el portal responde
        capture.take_screenshot(self._on_captured)

    def _on_captured(self, uri, error):
        self._capturing = False
        self.release()
        if error:
            print(f"pickscreen: {error}", file=sys.stderr)
        if not uri:
            if self.window:          # cancelado: volver al editor si existía
                self.window.set_visible(True)
            return

        pixbuf = self._load_capture(uri)
        if pixbuf is None:
            return
        if self.mode == "ocr":
            self._ocr_capture(pixbuf)
        else:
            self._open_editor(pixbuf)

    def _load_capture(self, uri):
        path = unquote(urlparse(uri).path)
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        except Exception as exc:  # noqa: BLE001
            print(f"pickscreen: no se pudo leer {path}: {exc}", file=sys.stderr)
            return None
        # El portal deja su propio archivo; el guardado lo gestiona output.py
        # para no duplicar capturas en la carpeta de destino.
        try:
            Gio.File.new_for_path(path).delete(None)
        except Exception:  # noqa: BLE001
            pass
        return pixbuf

    def _open_editor(self, pixbuf):
        if self.cfg.get("auto_copy"):
            output.copy_pixbuf(pixbuf)
        if self.cfg.get("auto_save"):
            try:
                saved = output.save_pixbuf(pixbuf, self.cfg)
                print(f"pickscreen: guardado en {saved}")
            except OSError as exc:
                print(f"pickscreen: no se pudo guardar: {exc}", file=sys.stderr)

        if self.window:
            self.window.destroy()
        self.window = EditorWindow(self, pixbuf, self.cfg)
        self.window.present()

    # -------------------------------------------------------- OCR sin editor
    def _ocr_capture(self, pixbuf):
        """`pickscreen ocr`: elegir una zona y dejar su texto en el portapapeles."""
        if not ocr.available():
            self._notify(_("Falta Tesseract"), ocr.install_hint().splitlines()[0])
            return
        self.hold()
        ocr.recognize_async(pixbuf, self._on_ocr_done, 6, self.cfg.get("ocr_langs"))

    def _on_ocr_done(self, text, error):
        if error:
            self._notify(_("No se pudo reconocer el texto"), error)
        elif not text:
            self._notify(_("No se encontró texto"), _("Prueba con otra zona."))
        else:
            output.copy_text(text)
            preview = text if len(text) <= 120 else text[:117] + "…"
            self._notify(_("Texto copiado ({n} caracteres)").format(n=len(text)), preview)
        # dar tiempo a que la notificación salga antes de que el proceso termine
        GLib.timeout_add_seconds(1, lambda: (self.release(), False)[1])

    def _notify(self, title, body):
        print(f"pickscreen: {title}: {body}", flush=True)
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        self.send_notification("pickscreen-ocr", notification)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("install", "uninstall", "gnome-print",
                                              "help", "--help", "-h"):
        from . import installer
        return installer.run(sys.argv[1:])
    return PickScreenApp().run(sys.argv)
