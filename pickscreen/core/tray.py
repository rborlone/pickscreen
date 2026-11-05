"""Ícono en la barra superior (StatusNotifierItem + menú dbusmenu), sin dependencias extra.

Lo muestran KDE, XFCE, Cinnamon, etc. En GNOME hace falta la extensión AppIndicator
(paquete `gnome-shell-extension-appindicator` en Fedora).
"""
import os

from gi.repository import Gio, GLib
from .i18n import _

SNI_XML = """<node><interface name="org.kde.StatusNotifierItem">
 <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
 <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
 <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
 <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
 <property name="Category" type="s" access="read"/><property name="Id" type="s" access="read"/>
 <property name="Title" type="s" access="read"/><property name="Status" type="s" access="read"/>
 <property name="WindowId" type="i" access="read"/><property name="IconName" type="s" access="read"/>
 <property name="ItemIsMenu" type="b" access="read"/><property name="Menu" type="o" access="read"/>
 <signal name="NewStatus"><arg type="s"/></signal>
</interface></node>"""

MENU_XML = """<node><interface name="com.canonical.dbusmenu">
 <method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
  <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
 <method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/>
  <arg type="a(ia{sv})" direction="out"/></method>
 <method name="GetProperty"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
 <method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method>
 <method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
 <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
 <method name="AboutToShowGroup"><arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/></method>
 <property name="Version" type="u" access="read"/><property name="TextDirection" type="s" access="read"/>
 <property name="Status" type="s" access="read"/><property name="IconThemePath" type="as" access="read"/>
 <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
</interface></node>"""

WATCHER = "org.kde.StatusNotifierWatcher"


class Tray:
    def __init__(self, icon_name, on_capture, on_ocr, on_record, on_quit, on_prefs=None):
        self.icon_name = icon_name
        self.recording = False
        self.revision = 1
        self.actions = {1: on_capture, 2: on_ocr, 3: on_record, 5: on_quit}
        if on_prefs:
            self.actions[6] = on_prefs
        self.conn = None
        self._objects = []
        self._owner = None
        self._watcher = None

    def start(self):
        self.conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        sni = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self._objects = [
            self.conn.register_object("/StatusNotifierItem", sni, self._sni_call, self._sni_get, None),
            self.conn.register_object("/MenuBar", menu, self._menu_call, self._menu_get, None)]
        self._owner = Gio.bus_own_name_on_connection(
            self.conn, self.name, Gio.BusNameOwnerFlags.NONE, None, None)
        # Si el anfitrión (extensión) aparece después, nos registramos de nuevo.
        self._watcher = Gio.bus_watch_name_on_connection(
            self.conn, WATCHER, Gio.BusNameWatcherFlags.NONE, lambda *_a: self._register(), None)

    def stop(self):
        """Quita el ícono de la barra (soltar el nombre basta para que el anfitrión lo retire)."""
        if self._watcher:
            Gio.bus_unwatch_name(self._watcher)
        if self._owner:
            Gio.bus_unown_name(self._owner)
        for obj_id in self._objects:
            self.conn.unregister_object(obj_id)
        self._objects, self._owner, self._watcher = [], None, None

    def _register(self):
        self.conn.call(WATCHER, "/StatusNotifierWatcher", WATCHER, "RegisterStatusNotifierItem",
                       GLib.Variant("(s)", (self.name,)), None, Gio.DBusCallFlags.NONE, -1, None, None)

    def set_recording(self, recording):
        self.recording = recording
        self.revision += 1
        self.conn.emit_signal(None, "/MenuBar", "com.canonical.dbusmenu", "LayoutUpdated",
                              GLib.Variant("(ui)", (self.revision, 0)))

    # ------------------------------------------------------ StatusNotifierItem
    def _sni_get(self, _c, _s, _p, _i, prop):
        values = {"Category": ("s", "ApplicationStatus"), "Id": ("s", "pickscreen"),
                  "Title": ("s", "pickscreen"), "Status": ("s", "Active"), "WindowId": ("i", 0),
                  "IconName": ("s", self.icon_name), "ItemIsMenu": ("b", False),
                  "Menu": ("o", "/MenuBar")}
        kind, value = values[prop]
        return GLib.Variant(kind, value)

    def _sni_call(self, _c, _s, _p, _i, method, _params, invocation):
        if method == "Activate":
            self.actions[1]()
        elif method == "SecondaryActivate":
            self.actions[3]()
        invocation.return_value(None)

    # ----------------------------------------------------------------- menú
    def _items(self):
        record = _("Detener grabación") if self.recording else _("Grabar pantalla")
        return [(1, {"label": _("Capturar pantalla")}),
                (2, {"label": _("Copiar texto de una zona (OCR)")}),
                (3, {"label": record}),
                (4, {"type": "separator"}),
                (6, {"label": _("Preferencias…")}),
                (5, {"label": _("Salir")})]

    @staticmethod
    def _props(raw):
        return {k: GLib.Variant("s", v) for k, v in raw.items()}

    def _menu_get(self, _c, _s, _p, _i, prop):
        return {"Version": GLib.Variant("u", 3), "TextDirection": GLib.Variant("s", "ltr"),
                "Status": GLib.Variant("s", "normal"),
                "IconThemePath": GLib.Variant("as", [])}[prop]

    def _menu_call(self, _c, _s, _p, _i, method, params, invocation):
        if method == "GetLayout":
            children = [GLib.Variant("(ia{sv}av)", (i, self._props(p), [])) for i, p in self._items()]
            root = (0, {"children-display": GLib.Variant("s", "submenu")}, children)
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self.revision, root)))
        elif method == "GetGroupProperties":
            invocation.return_value(GLib.Variant(
                "(a(ia{sv}))", ([(i, self._props(p)) for i, p in self._items()],)))
        elif method == "GetProperty":
            item, name = params.unpack()[:2]
            raw = dict(self._items()).get(item, {})
            invocation.return_value(GLib.Variant("(v)", (GLib.Variant("s", raw.get(name, "")),)))
        elif method == "Event":
            item, event = params.unpack()[:2]
            self._event(item, event)
            invocation.return_value(None)
        elif method == "EventGroup":
            for item, event, _d, _t in params.unpack()[0]:
                self._event(item, event)
            invocation.return_value(GLib.Variant("(ai)", ([],)))
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method == "AboutToShowGroup":
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))

    def _event(self, item, event):
        if event == "clicked" and item in self.actions:
            GLib.idle_add(lambda: (self.actions[item](), False)[1])
