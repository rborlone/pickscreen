"""Ventana pequeña de la grabación: cronómetro y botón de detener; al terminar, acciones sobre el archivo."""
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from ..core import gif
from ..core.i18n import _


class RecordingWindow(Adw.Window):
    def __init__(self, app, on_stop):
        super().__init__(application=app, title="pickscreen", resizable=False,
                         default_width=340, modal=False)
        self.on_stop = on_stop
        self.path = None
        self._t0 = time.monotonic()
        self._tick = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        self.status = Gtk.Label(label=_("Grabando…"), css_classes=["title-3"])
        self.clock = Gtk.Label(label="00:00", css_classes=["title-1", "numeric"])
        self.detail = Gtk.Label(wrap=True, xalign=0.5, css_classes=["dim-label"], visible=False)
        self.bar = Gtk.ProgressBar(visible=False)
        self.stop_btn = Gtk.Button(label=_("Detener"), css_classes=["destructive-action", "pill"],
                                   halign=Gtk.Align.CENTER)
        self.stop_btn.connect("clicked", lambda _b: self.on_stop())

        self.actions = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, visible=False)
        self.open_btn = self._button(_("Abrir"), self._open)
        self.folder_btn = self._button(_("Carpeta"), self._show_folder)
        self.gif_btn = self._button(_("Exportar GIF"), self._export_gif)
        self.gif_btn.set_sensitive(gif.available())
        if not gif.available():
            self.gif_btn.set_tooltip_text(_("Instala Pillow (python3-pillow) para exportar GIF"))
        for b in (self.open_btn, self.folder_btn, self.gif_btn):
            self.actions.append(b)

        for w in (self.status, self.clock, self.detail, self.bar, self.stop_btn, self.actions):
            box.append(w)
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(Adw.HeaderBar())
        self.set_content(view)
        self._tick = GLib.timeout_add(500, self._update_clock)

    def _button(self, label, handler):
        b = Gtk.Button(label=label)
        b.connect("clicked", lambda _b: handler())
        return b

    def _update_clock(self):
        s = int(time.monotonic() - self._t0)
        self.clock.set_label(f"{s // 60:02d}:{s % 60:02d}")
        return True

    # ----------------------------------------------------------- estados
    def show_done(self, path, error):
        if self._tick:
            GLib.source_remove(self._tick)
            self._tick = None
        self.stop_btn.set_visible(False)
        self.path = path
        if path:
            self.status.set_label(_("Grabación guardada"))
            self.detail.set_label(str(path))
            self.actions.set_visible(True)
        else:
            self.status.set_label(_("No se pudo grabar"))
            self.detail.set_label(error or _("No se generó ningún archivo."))
        self.detail.set_visible(True)

    def _open(self):
        Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(str(self.path)).get_uri(), None)

    def _show_folder(self):
        Gio.AppInfo.launch_default_for_uri(
            Gio.File.new_for_path(str(self.path.parent)).get_uri(), None)

    def _export_gif(self):
        self.gif_btn.set_sensitive(False)
        self.bar.set_visible(True)
        self.status.set_label(_("Creando GIF…"))
        gif.export_async(self.path, self._gif_done, self.bar.set_fraction)

    def _gif_done(self, out, error):
        self.bar.set_visible(False)
        self.gif_btn.set_sensitive(True)
        self.status.set_label(_("GIF creado") if out else _("No se pudo crear el GIF"))
        self.detail.set_label(str(out) if out else error)
        return False
