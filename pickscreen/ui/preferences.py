"""Diálogo de preferencias. Los cambios se guardan al momento y se aplican a la siguiente captura."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from ..core import config, ocr
from ..core.i18n import LANGUAGES, system_language
from ..core.shortcuts import SHORTCUTS
from ..core.i18n import _

FORMATS = ["png", "jpg"]
LANG_NAMES = {"spa": "Español", "eng": "Inglés", "por": "Portugués", "fra": "Francés",
              "deu": "Alemán", "ita": "Italiano", "cat": "Catalán"}


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, cfg: dict, app=None):
        super().__init__(title=_("Preferencias"))
        self.cfg = cfg          # el mismo dict que usa la app: se modifica en el lugar
        self.app = app

        page = Adw.PreferencesPage()
        page.add(self._build_captures_group())
        page.add(self._build_video_group())
        page.add(self._build_ocr_group())
        page.add(self._build_shortcuts_group())
        page.add(self._build_general_group())
        self.add(page)

    def _set(self, key, value):
        self.cfg[key] = value
        config.save(self.cfg)

    # -------------------------------------------------------------- capturas
    def _build_captures_group(self):
        group = Adw.PreferencesGroup(title=_("Capturas"))

        self.folder_row = Adw.ActionRow(title=_("Carpeta de guardado"))
        choose = Gtk.Button(label=_("Elegir…"), valign=Gtk.Align.CENTER)
        choose.connect("clicked", self._choose_folder)
        self.reset_btn = Gtk.Button(icon_name="edit-undo-symbolic", valign=Gtk.Align.CENTER,
                                    css_classes=["flat"],
                                    tooltip_text=_("Volver a la carpeta por defecto"))
        self.reset_btn.connect("clicked", lambda _b: self._folder_changed(None))
        self.folder_row.add_suffix(self.reset_btn)
        self.folder_row.add_suffix(choose)
        group.add(self.folder_row)
        self._refresh_folder()

        self.switches = {}
        for key, title, subtitle in (
            ("auto_save", _("Guardar automáticamente"), _("Cada captura se guarda como archivo.")),
            ("auto_copy", _("Copiar automáticamente"), _("Cada captura queda en el portapapeles.")),
        ):
            row = Adw.SwitchRow(title=title, subtitle=subtitle, active=bool(self.cfg.get(key)))
            row.connect("notify::active", lambda r, _p, k=key: self._set(k, r.get_active()))
            group.add(row)
            self.switches[key] = row

        self.format_row = fmt = Adw.ComboRow(title=_("Formato de imagen"),
                                             model=Gtk.StringList.new(["PNG", "JPG"]))
        fmt.set_selected(FORMATS.index(self.cfg.get("format")) if self.cfg.get("format") in FORMATS else 0)
        self.quality_row = Adw.SpinRow.new_with_range(50, 100, 1)
        self.quality_row.set_title(_("Calidad del JPG"))
        self.quality_row.set_value(self.cfg.get("jpg_quality", 92))
        self.quality_row.set_visible(fmt.get_selected() == 1)
        self.quality_row.connect("notify::value",
                                 lambda r, _p: self._set("jpg_quality", int(r.get_value())))

        def format_changed(row, _p):
            self._set("format", FORMATS[row.get_selected()])
            self.quality_row.set_visible(row.get_selected() == 1)

        fmt.connect("notify::selected", format_changed)
        group.add(fmt)
        group.add(self.quality_row)
        return group

    def _refresh_folder(self):
        self.folder_row.set_subtitle(str(config.save_dir(self.cfg)))
        self.reset_btn.set_visible(bool(self.cfg.get("save_dir")))

    def _folder_changed(self, path):
        self._set("save_dir", path)
        self._refresh_folder()

    def _choose_folder(self, _button):
        dialog = Gtk.FileDialog(title=_("Carpeta de guardado"))
        current = config.save_dir(self.cfg)
        if current.is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(str(current)))

        def done(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
            except GLib.Error:        # cerró el selector sin elegir
                return
            if folder and folder.get_path():
                self._folder_changed(folder.get_path())

        dialog.select_folder(self.get_root(), None, done)

    # ----------------------------------------------------------------- vídeo
    def _build_video_group(self):
        group = Adw.PreferencesGroup(title=_("Grabación de pantalla"))
        self.video_folder_row = row = Adw.ActionRow(title=_("Carpeta de vídeos"),
                                                    subtitle=str(config.video_dir(self.cfg)))
        choose = Gtk.Button(label=_("Elegir…"), valign=Gtk.Align.CENTER)

        def chosen(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
            except GLib.Error:
                return
            if folder and folder.get_path():
                self._set("video_dir", folder.get_path())
                row.set_subtitle(folder.get_path())

        choose.connect("clicked", lambda _b: Gtk.FileDialog(title=_("Carpeta de vídeos"))
                       .select_folder(self.get_root(), None, chosen))
        row.add_suffix(choose)
        group.add(row)

        self.audio_row = Adw.SwitchRow(title=_("Grabar micrófono"),
                                       subtitle=_("Añade el audio del micrófono al vídeo."),
                                       active=bool(self.cfg.get("video_audio")))
        self.audio_row.connect("notify::active",
                               lambda r, _p: self._set("video_audio", r.get_active()))
        group.add(self.audio_row)
        return group

    # ------------------------------------------------------------------- OCR
    def _build_ocr_group(self):
        group = Adw.PreferencesGroup(title=_("Reconocimiento de texto (OCR)"))
        options = [(_("Automático (español + inglés)"), None)]
        if ocr.available():
            options += [(_(LANG_NAMES.get(code, code)), [code])
                        for code in ocr.installed_languages() if code != "osd"]
        self.ocr_row = row = Adw.ComboRow(title=_("Idioma del texto"),
                                          model=Gtk.StringList.new([name for name, _v in options]))
        current = self.cfg.get("ocr_langs")
        row.set_selected(next((i for i, (_n, v) in enumerate(options) if v == current), 0))
        row.connect("notify::selected", lambda r, _p: self._set("ocr_langs", options[r.get_selected()][1]))
        if not ocr.available():
            row.set_sensitive(False)
            row.set_subtitle(_("Tesseract no está instalado"))
        else:
            row.set_subtitle(_("Idiomas instalados en Tesseract"))
        group.add(row)
        return group

    # ---------------------------------------------------------------- atajos
    def _build_shortcuts_group(self):
        group = Adw.PreferencesGroup(
            title=_("Atajos de teclado"),
            description=_("Se cambian en la configuración del escritorio (en GNOME: Configuración → "
                          "Teclado → Atajos). También puedes asociar el comando de cada fila a una tecla."))
        triggers = self.app.shortcut_triggers() if self.app else {}
        commands = {"capture": "pickscreen capture", "ocr": "pickscreen ocr", "record": "pickscreen record"}
        for sid, desc, _suggested in SHORTCUTS:
            row = Adw.ActionRow(title=_(desc), subtitle=commands[sid], subtitle_selectable=True)
            keys = Gtk.Label(label=triggers.get(sid) or _("Sin asignar"), css_classes=["dim-label"],
                             valign=Gtk.Align.CENTER)
            row.add_suffix(keys)
            group.add(row)
        return group

    # --------------------------------------------------------------- general
    def _build_general_group(self):
        group = Adw.PreferencesGroup(title=_("General"))
        row = Adw.SwitchRow(title=_("Mostrar ícono en la bandeja"),
                            subtitle=_("Ícono en la barra superior con acceso rápido. "
                                       "En GNOME requiere la extensión AppIndicator."),
                            active=bool(self.cfg.get("tray", True)))

        def toggled(r, _p):
            self._set("tray", r.get_active())
            if self.app:
                self.app.set_tray_enabled(r.get_active())

        row.connect("notify::active", toggled)
        group.add(row)

        options = [(_("Automático (idioma del sistema: {lang})").format(lang=LANGUAGES[system_language()]), None)] + [(name, code) for code, name in LANGUAGES.items()]
        lang_row = Adw.ComboRow(title=_("Idioma de la interfaz"),
                                model=Gtk.StringList.new([name for name, _c in options]))
        current = self.cfg.get("language")
        lang_row.set_selected(next((i for i, (_n, c) in enumerate(options) if c == current), 0))

        def lang_changed(r, _p):
            code = options[r.get_selected()][1]
            if code == self.cfg.get("language"):
                return
            self._set("language", code)
            toast = Adw.Toast(title=_("Reinicia pickscreen para aplicar el idioma."), timeout=0)
            if self.app:
                toast.set_button_label(_("Reiniciar"))
                toast.connect("button-clicked", lambda _t: self.app.restart())
            self.add_toast(toast)

        lang_row.connect("notify::selected", lang_changed)
        group.add(lang_row)
        return group
