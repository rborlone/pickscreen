"""Llamadas a xdg-desktop-portal que responden con una señal `Response`."""
import itertools
import os

from gi.repository import Gio, GLib

BUS_NAME = "org.freedesktop.portal.Desktop"
OBJ_PATH = "/org/freedesktop/portal/desktop"
_counter = itertools.count()


APP_ID = "cl.pickscreen.App"
_registered = None
register_error = None       # por qué falló el registro, si falló


def connection():
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def registered_connection():
    """Conexión propia, registrada ante el portal con el id de la app.

    El portal decide quién es una conexión en la PRIMERA petición que recibe. En
    una app GTK, la conexión compartida ya habló con el portal antes de que
    podamos registrarnos (p. ej. para leer el tema), así que no sirve.
    Hace falta que el .desktop de la app esté instalado (`pickscreen install`).
    """
    global _registered, register_error
    if _registered is None:
        address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
        _registered = Gio.DBusConnection.new_for_address_sync(
            address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
        try:
            _registered.call_sync(
                BUS_NAME, OBJ_PATH, "org.freedesktop.host.portal.Registry", "Register",
                GLib.Variant("(sa{sv})", (APP_ID, {})), None,
                Gio.DBusCallFlags.NONE, 2000, None)
        except GLib.Error as exc:
            register_error = exc.message
    return _registered


def new_token(prefix: str = "pickscreen") -> str:
    return f"{prefix}_{os.getpid()}_{next(_counter)}"


def request(interface: str, method: str, make_args, callback, conn=None) -> None:
    """Llama a `method` y entrega la respuesta del portal.

    - `make_args(token)` devuelve el GLib.Variant con TODOS los argumentos;
      `token` debe ir como `handle_token` en las opciones.
    - `callback(code, results)`: `code` es 0 (ok), 1 (cancelado) u otro (fallo).
      Si la llamada ni siquiera llegó al portal, `code` es None y
      `results` es {"error": mensaje}.
    """
    conn = conn or connection()
    token = new_token()
    sender = conn.get_unique_name()[1:].replace(".", "_")
    request_path = f"{OBJ_PATH}/request/{sender}/{token}"
    sub = {}

    def on_response(_conn, _sender, _path, _iface, _signal, params, *_):
        conn.signal_unsubscribe(sub["id"])
        code, results = params.unpack()
        callback(code, results)

    # Nos suscribimos ANTES de llamar, para no perder la respuesta.
    sub["id"] = conn.signal_subscribe(
        BUS_NAME, "org.freedesktop.portal.Request", "Response", request_path,
        None, Gio.DBusSignalFlags.NONE, on_response,
    )

    def on_done(source, result):
        try:
            source.call_finish(result)
        except GLib.Error as exc:
            conn.signal_unsubscribe(sub["id"])
            callback(None, {"error": exc.message})

    conn.call(BUS_NAME, OBJ_PATH, interface, method, make_args(token), None,
              Gio.DBusCallFlags.NONE, -1, None, on_done)
