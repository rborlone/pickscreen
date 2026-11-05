"""Atajos de teclado globales vía el portal GlobalShortcuts.

El portal pide al usuario que confirme o cambie las teclas (en GNOME se
ajustan después en Configuración). Si el escritorio no lo soporta, el servicio
sigue funcionando y el atajo se asocia a mano con el comando `pickscreen capture`.
"""
from gi.repository import Gio, GLib

from . import portal
from .i18n import _

IFACE = "org.freedesktop.portal.GlobalShortcuts"
# (id, descripción, tecla sugerida). El usuario puede cambiarla.
SHORTCUTS = [
    ("capture", "Capturar pantalla", "CTRL+ALT+P"),
    ("ocr", "Copiar texto de una zona (OCR)", "CTRL+ALT+O"),
    ("record", "Grabar pantalla (iniciar/detener)", "CTRL+ALT+R"),
]


class GlobalShortcuts:
    def __init__(self, on_activate, on_status=print, bind=True):
        self.on_activate = on_activate    # on_activate(shortcut_id)
        self.on_status = on_status        # mensajes para el usuario / el journal
        self.bind = bind
        self.conn = None
        self.session = None
        self.known = []
        self.triggers = {}                # id -> descripción de la tecla asignada

    def start(self):
        # Conexión propia y registrada: ver portal.registered_connection().
        self.conn = portal.registered_connection()
        portal.request(IFACE, "CreateSession", self._create_args, self._on_session, self.conn)

    # --- sesión ---
    def _create_args(self, token):
        return GLib.Variant("(a{sv})", ({
            "handle_token": GLib.Variant("s", token),
            "session_handle_token": GLib.Variant("s", portal.new_token("pickscreen_session")),
        },))

    def _on_session(self, code, results):
        if code != 0:
            detail = results.get("error") if code is None else f"código {code}"
            hint = ("Instala la app con `pickscreen install` para activarlos. "
                    if portal.register_error and "App info not found" in portal.register_error else "")
            self.on_status(f"Atajos globales no disponibles ({detail}). {hint}"
                           "Mientras tanto, asocia el comando `pickscreen capture` a una tecla.")
            return
        self.session = results["session_handle"]
        self.conn.signal_subscribe(
            portal.BUS_NAME, IFACE, "Activated", portal.OBJ_PATH, None,
            Gio.DBusSignalFlags.NONE, self._on_activated)
        portal.request(IFACE, "ListShortcuts",
                       lambda t: GLib.Variant("(oa{sv})", (self.session,
                                              {"handle_token": GLib.Variant("s", t)})),
                       self._on_listed, self.conn)

    def _on_listed(self, code, results):
        self._remember(results if code == 0 else {})
        self.known = list(self.triggers)
        missing = [s for s in SHORTCUTS if s[0] not in self.known]
        if not missing:
            self.on_status("Atajos globales listos.")
        elif self.bind:
            self._bind(missing)

    def _remember(self, results):
        for sid, info in results.get("shortcuts", []):
            self.triggers[sid] = info.get("trigger_description", "")

    def _bind(self, shortcuts):
        # Solo se piden los que faltan, para no volver a preguntar en cada inicio.
        entries = [(sid, {"description": GLib.Variant("s", _(desc)),
                          "preferred_trigger": GLib.Variant("s", trigger)})
                   for sid, desc, trigger in shortcuts]

        def args(token):
            return GLib.Variant("(oa(sa{sv})sa{sv})", (
                self.session, entries, "", {"handle_token": GLib.Variant("s", token)}))

        def done(code, results):
            if code == 0:
                self._remember(results)
            self.on_status("Atajos globales listos." if code == 0
                           else "No se asignaron atajos globales (puedes hacerlo en Configuración).")

        portal.request(IFACE, "BindShortcuts", args, done, self.conn)

    def _on_activated(self, _conn, _sender, _path, _iface, _signal, params, *_):
        session, shortcut_id, _timestamp, _options = params.unpack()
        if session == self.session:
            self.on_activate(shortcut_id)
