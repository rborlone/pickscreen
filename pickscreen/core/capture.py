"""Captura de pantalla vía xdg-desktop-portal (funciona en GNOME, KDE, wlroots y X11)."""
from gi.repository import GLib

from . import portal
from .i18n import _


def take_screenshot(callback, interactive: bool = True) -> None:
    """Pide una captura al portal. `callback(uri, error)`.

    - captura correcta: `uri` es un file:// y `error` es None
    - cancelada por el usuario: ambos None
    - fallo: `error` es un texto
    """
    def make_args(token):
        options = {
            "handle_token": GLib.Variant("s", token),
            "interactive": GLib.Variant("b", interactive),
        }
        return GLib.Variant("(sa{sv})", ("", options))

    def on_result(code, results):
        if code == 0:
            callback(results.get("uri"), None)
        elif code == 1:
            callback(None, None)
        elif code is None:
            callback(None, _("No se pudo contactar al portal: {error}").format(error=results["error"]))
        elif code == 2 and not results:
            # GNOME responde así cuando el visor se cierra sin devolver una imagen.
            callback(None, _("El visor se cerró sin devolver una imagen (¿se canceló la captura?)."))
        else:
            callback(None, _("El portal no pudo completar la captura "
                             "(código {code}, resultados: {results}).")
                     .format(code=code, results=results))

    portal.request("org.freedesktop.portal.Screenshot", "Screenshot", make_args, on_result)
