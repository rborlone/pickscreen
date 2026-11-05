"""Ventana del editor: vista de la captura, recorte y anotaciones."""
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, GLib, Gtk

from ..core import annotations as ann
from ..core import ocr, output
from .glyphs import Glyph
from ..core.i18n import _

TOOLS = [
    ("crop", _("Recorte")), ("arrow", _("Flecha")), ("line", _("Línea")),
    ("rect", _("Rectángulo")), ("ellipse", _("Elipse")), ("pen", _("Lápiz")),
    ("highlight", _("Resaltador")), ("text", _("Texto")), ("step", _("Número de paso")),
    ("pixelate", _("Pixelar")), ("ocr", _("Copiar texto de una zona (OCR)")),
]
LABELS = dict(TOOLS)
KEYS = {name: str((i + 1) % 10) for i, (name, _l) in enumerate(TOOLS)}
KEYS["ocr"] = "o"
# Cada fila es un botón de la barra; los que tienen varias herramientas llevan menú.
TOOL_GROUPS = [
    ["crop"],
    ["rect", "ellipse", "line", "arrow"],
    ["pen", "highlight"],
    ["text"],
    ["step"],
    ["pixelate"],
    ["ocr"],
]
SHAPE_TOOLS = {"arrow", "line", "rect", "ellipse"}
DEFAULT_COLOR = (0.88, 0.1, 0.1, 1.0)
PALETTE = [  # rojo, naranja, amarillo, verde, celeste, azul / morado, rosa, negro, gris, blanco
    (0.88, 0.10, 0.10), (0.96, 0.52, 0.10), (0.98, 0.82, 0.10), (0.16, 0.68, 0.30),
    (0.10, 0.70, 0.85), (0.15, 0.40, 0.92), (0.55, 0.25, 0.80), (0.93, 0.35, 0.65),
    (0.0, 0.0, 0.0), (0.45, 0.45, 0.45), (0.80, 0.80, 0.80), (1.0, 1.0, 1.0),
]
WIDTH_PRESETS = [2, 4, 8, 14]


class EditorWindow(Adw.ApplicationWindow):
    def __init__(self, app, pixbuf, cfg):
        super().__init__(application=app, title="pickscreen")
        self.app = app
        self.cfg = cfg

        self.pixbuf = pixbuf
        self.base = ann.surface_from_pixbuf(pixbuf)
        self.anns = []             # anotaciones confirmadas
        self.draft = None          # anotación en curso (mientras se arrastra)
        self.selection = None      # (x, y, w, h) del recorte, en coords de imagen
        self.undo_stack = []       # estados anteriores: (pixbuf, anotaciones)
        self.redo_stack = []

        self.tool = "arrow"
        self.color = DEFAULT_COLOR
        self.width = 4

        self.revision = 0          # sube con cada cambio
        self.copied_rev = 0        # revisión que ya está en el portapapeles
        self.saved_rev = 0         # revisión ya guardada en archivo (0 = la captura original)

        self.set_default_size(
            min(max(pixbuf.get_width() + 40, 720), 1400),
            min(max(pixbuf.get_height() + 160, 520), 900),
        )

        # --- barra superior ---
        header = Adw.HeaderBar()
        new_btn = Gtk.Button(icon_name="camera-photo-symbolic", tooltip_text=_("Nueva captura"))
        new_btn.connect("clicked", lambda *_: app.new_capture())
        header.pack_start(new_btn)

        self.undo_btn = Gtk.Button(icon_name="edit-undo-symbolic", sensitive=False,
                                   tooltip_text=_("Deshacer (Ctrl+Z)"))
        self.undo_btn.connect("clicked", lambda *_: self.undo())
        self.redo_btn = Gtk.Button(icon_name="edit-redo-symbolic", sensitive=False,
                                   tooltip_text=_("Rehacer (Ctrl+Shift+Z)"))
        self.redo_btn.connect("clicked", lambda *_: self.redo())
        header.pack_start(self.undo_btn)
        header.pack_start(self.redo_btn)

        save_btn = Gtk.Button(label=_("Guardar"), tooltip_text=_("Guardar archivo (Ctrl+S)"))
        save_btn.connect("clicked", lambda *_: self.save())
        header.pack_end(save_btn)
        copy_btn = Gtk.Button(label=_("Copiar"), css_classes=["suggested-action"],
                              tooltip_text=_("Copiar al portapapeles (Ctrl+C)"))
        copy_btn.connect("clicked", lambda *_: self.copy())
        header.pack_end(copy_btn)
        text_btn = Gtk.Button(child=Glyph("ocr"), tooltip_text=_("Copiar todo el texto de la imagen (OCR)"))
        text_btn.connect("clicked", lambda *_: self.ocr_all())
        header.pack_end(text_btn)
        prefs_btn = Gtk.Button(icon_name="emblem-system-symbolic",
                               tooltip_text=_("Preferencias (Ctrl+,)"))
        prefs_btn.connect("clicked", lambda *_: self.open_preferences())
        header.pack_end(prefs_btn)

        # --- barra de herramientas ---
        bar = Gtk.Box(spacing=6, margin_start=12, margin_end=12, margin_top=6, margin_bottom=6)
        self.groups = []
        first_toggle = None
        for tools in TOOL_GROUPS:
            widget, toggle = self._build_tool_group(tools, first_toggle)
            first_toggle = first_toggle or toggle
            bar.append(widget)
        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin_start=4, margin_end=4))
        bar.append(self._build_color_button())
        bar.append(self._build_width_button())
        bar.append(Gtk.Box(hexpand=True))   # empuja «Aplicar recorte» a la derecha

        self.crop_btn = Gtk.Button(label=_("Aplicar recorte"), css_classes=["suggested-action"],
                                   visible=False)
        self.crop_btn.connect("clicked", lambda *_: self.crop())
        bar.append(self.crop_btn)

        bar_scroll = Gtk.ScrolledWindow(child=bar, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                        hscrollbar_policy=Gtk.PolicyType.AUTOMATIC)

        # --- lienzo ---
        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.area.set_draw_func(self._draw)
        self.area.set_cursor_from_name("crosshair")
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.area.add_controller(drag)

        self.toasts = Adw.ToastOverlay(child=self.area)
        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(bar_scroll)
        self.set_content(view)

        # --- atajos ---
        keys = Gtk.ShortcutController()
        shortcuts = [("<Control>c", self.copy), ("<Control>s", self.save),
                     ("<Control>z", self.undo), ("<Control><Shift>z", self.redo),
                     ("<Control>y", self.redo), ("Escape", self._escape),
                     ("Return", self.crop), ("<Control>comma", self.open_preferences)]
        shortcuts += [(self._key_for(n), lambda n=n: self._select_tool(n)) for n, _l in TOOLS]
        for accel, fn in shortcuts:
            keys.add_shortcut(Gtk.Shortcut(
                trigger=Gtk.ShortcutTrigger.parse_string(accel),
                action=Gtk.CallbackAction.new(lambda *_a, f=fn: (f(), True)[1]),
            ))
        self.add_controller(keys)
        self.connect("close-request", lambda *_: (self.finish(), False)[1])

    @staticmethod
    def _key_for(tool):
        return KEYS[tool]

    # ------------------------------------------------------------ geometría
    def _layout(self, width, height):
        iw, ih = self.pixbuf.get_width(), self.pixbuf.get_height()
        scale = min(width / iw, height / ih, 1.0)
        return scale, (width - iw * scale) / 2, (height - ih * scale) / 2

    def _to_image(self, x, y):
        scale, ox, oy = self._layout(self.area.get_width(), self.area.get_height())
        ix = min(max((x - ox) / scale, 0), self.pixbuf.get_width())
        iy = min(max((y - oy) / scale, 0), self.pixbuf.get_height())
        return ix, iy

    # --------------------------------------------------------------- dibujo
    def _draw(self, _area, cr, width, height):
        scale, ox, oy = self._layout(width, height)
        iw, ih = self.pixbuf.get_width(), self.pixbuf.get_height()
        cr.translate(ox, oy)
        cr.scale(scale, scale)
        cr.set_source_surface(self.base, 0, 0)
        cr.paint()
        for a in self.anns:
            ann.draw(cr, a, self.base)
        if self.draft:
            ann.draw(cr, self.draft, self.base)
        if self.selection:
            x, y, w, h = self.selection
            cr.set_source_rgba(0, 0, 0, 0.5)       # oscurece lo que queda fuera
            cr.rectangle(0, 0, iw, ih)
            cr.rectangle(x, y, w, h)
            cr.set_fill_rule(cairo.FillRule.EVEN_ODD)
            cr.fill()
            cr.set_source_rgba(1, 1, 1, 0.95)
            cr.set_line_width(1.5 / scale)
            cr.set_dash([6 / scale, 4 / scale])
            cr.rectangle(x, y, w, h)
            cr.stroke()

    # ----------------------------------------------------------- herramientas
    def _build_tool_group(self, tools, first_toggle):
        """Un botón de herramienta; si hay varias, añade un menú para elegir."""
        group = {"tools": tools, "current": self.tool if self.tool in tools else tools[0]}
        group["icon"] = Glyph(group["current"])
        group["toggle"] = toggle = Gtk.ToggleButton(child=group["icon"],
                                                    active=self.tool in tools)
        if first_toggle:
            toggle.set_group(first_toggle)
        toggle.connect("toggled", lambda b, g=group: b.get_active() and self._activate(g["current"]))
        self.groups.append(group)
        self._refresh_tip(group)
        if len(tools) == 1:
            return toggle, toggle

        popover = Gtk.Popover()
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for name in tools:
            row = Gtk.Box(spacing=10)
            row.append(Glyph(name))
            row.append(Gtk.Label(label=LABELS[name], xalign=0, hexpand=True))
            row.append(Gtk.Label(label=self._key_for(name), css_classes=["dim-label"]))
            item = Gtk.Button(child=row, css_classes=["flat"])
            item.connect("clicked", lambda _b, n=name, p=popover: (self._select_tool(n), p.popdown()))
            column.append(item)
        popover.set_child(column)
        menu = Gtk.MenuButton(popover=popover, icon_name="pan-down-symbolic",
                              tooltip_text=_("Más herramientas"))
        box = Gtk.Box(css_classes=["linked"])
        box.append(toggle)
        box.append(menu)
        return box, toggle

    def _refresh_tip(self, group):
        name = group["current"]
        group["toggle"].set_tooltip_text(f"{LABELS[name]} ({self._key_for(name)})")

    def _select_tool(self, name):
        """Elige una herramienta (desde un menú o un atajo) y actualiza su botón."""
        for group in self.groups:
            if name in group["tools"]:
                group["current"] = name
                group["icon"].set_kind(name)
                self._refresh_tip(group)
                if group["toggle"].get_active():
                    self._activate(name)
                else:
                    group["toggle"].set_active(True)   # su manejador activa la herramienta
                return

    def _activate(self, name):
        self.tool = name
        self.draft = None
        self._set_selection(None)
        self.area.queue_draw()

    def _build_color_button(self):
        self.color_glyph = Glyph("swatch", self.color, width=22, height=22)
        popover = Gtk.Popover()
        grid = Gtk.Grid(row_spacing=4, column_spacing=4)
        for i, rgb in enumerate(PALETTE):
            color = (*rgb, 1.0)
            swatch = Gtk.Button(child=Glyph("swatch", color, width=24, height=24),
                                css_classes=["flat"])
            swatch.connect("clicked", lambda _b, c=color, p=popover: (self._set_color(c), p.popdown()))
            grid.attach(swatch, i % 6, i // 6, 1, 1)
        custom = Gtk.Button(label=_("Personalizado…"))
        custom.connect("clicked", lambda _b: (popover.popdown(), self._choose_custom_color()))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_start=8, margin_end=8, margin_top=8, margin_bottom=8)
        box.append(grid)
        box.append(custom)
        popover.set_child(box)
        return Gtk.MenuButton(child=self.color_glyph, popover=popover, tooltip_text=_("Color"))

    def _set_color(self, color):
        self.color = color
        self.color_glyph.set_value(color)

    def _choose_custom_color(self):
        dialog = Gtk.ColorDialog(with_alpha=False)
        initial = Gdk.RGBA()
        initial.red, initial.green, initial.blue, initial.alpha = self.color

        def done(dlg, result):
            try:
                c = dlg.choose_rgba_finish(result)
            except GLib.Error:        # cerró el diálogo sin elegir
                return
            self._set_color((c.red, c.green, c.blue, 1.0))

        dialog.choose_rgba(self, initial, None, done)

    def _build_width_button(self):
        self.width_glyph = Glyph("linew", self.width, width=40, height=22)
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_start=8, margin_end=8, margin_top=8, margin_bottom=8)
        presets = Gtk.Box(spacing=4)
        for w in WIDTH_PRESETS:
            btn = Gtk.Button(child=Glyph("linew", w, width=40, height=22), css_classes=["flat"],
                             tooltip_text=f"{w} px")
            btn.connect("clicked", lambda _b, w=w, p=popover: (self._set_width(w), p.popdown()))
            presets.append(btn)
        self.width_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 30, 1)
        self.width_scale.set_value(self.width)
        self.width_scale.set_size_request(220, -1)
        self.width_scale.set_draw_value(True)
        self.width_scale.connect("value-changed",
                                 lambda s: self._set_width(s.get_value(), from_scale=True))
        box.append(presets)
        box.append(self.width_scale)
        popover.set_child(box)
        return Gtk.MenuButton(child=self.width_glyph, popover=popover, tooltip_text=_("Grosor"))

    def _set_width(self, width, from_scale=False):
        self.width = float(width)
        self.width_glyph.set_value(self.width)
        if not from_scale:
            self.width_scale.set_value(self.width)

    def _escape(self):
        self.draft = None
        self._set_selection(None)

    # --------------------------------------------------------------- ratón
    # Los manejadores de gesto solo convierten coordenadas; la lógica está en
    # _begin/_update/_end, que trabajan en coordenadas de imagen.
    def _on_drag_begin(self, _g, x, y):
        self._begin(*self._to_image(x, y))

    def _on_drag_update(self, gesture, dx, dy):
        _ok, sx, sy = gesture.get_start_point()
        self._update(*self._to_image(sx + dx, sy + dy))

    def _on_drag_end(self, gesture, dx, dy):
        _ok, sx, sy = gesture.get_start_point()
        self._update(*self._to_image(sx + dx, sy + dy))
        self._end()

    def _begin(self, x, y):
        self._origin = (x, y)
        tool = self.tool
        if tool in ("crop", "ocr"):
            self._set_selection(None)
        elif tool in SHAPE_TOOLS:
            self.draft = ann.Shape(tool, (x, y), (x, y), self.color, self.width)
        elif tool in ("pen", "highlight"):
            self.draft = ann.Stroke([(x, y)], self.color, self.width, tool == "highlight")
        elif tool == "pixelate":
            self.draft = ann.Pixelate((x, y, 0, 0), max(6, int(self.width * 3)))
        elif tool == "step":
            number = sum(isinstance(a, ann.Step) for a in self.anns) + 1
            self._commit(ann.Step((x, y), number, self.color, self.width))
        elif tool == "text":
            self._ask_text(x, y)
        self.area.queue_draw()

    def _update(self, x, y):
        x0, y0 = self._origin
        if self.tool in ("crop", "ocr"):
            w, h = abs(x - x0), abs(y - y0)
            self._set_selection((min(x, x0), min(y, y0), w, h) if w >= 2 and h >= 2 else None)
        elif isinstance(self.draft, ann.Shape):
            self.draft.p1 = (x, y)
        elif isinstance(self.draft, ann.Stroke):
            self.draft.points.append((x, y))
        elif isinstance(self.draft, ann.Pixelate):
            self.draft.rect = (min(x, x0), min(y, y0), abs(x - x0), abs(y - y0))
        self.area.queue_draw()

    def _end(self):
        if self.tool == "ocr":
            if self.selection:
                self.ocr_region(self.selection)
            return
        d, self.draft = self.draft, None
        if d is None:
            return
        if isinstance(d, ann.Shape):
            (x0, y0), (x1, y1) = d.p0, d.p1
            ok = abs(x1 - x0) + abs(y1 - y0) >= 3
        elif isinstance(d, ann.Pixelate):
            ok = d.rect[2] >= 4 and d.rect[3] >= 4
        else:
            ok = True
        if ok:
            self._commit(d)
        self.area.queue_draw()

    def _ask_text(self, ix, iy):
        scale, ox, oy = self._layout(self.area.get_width(), self.area.get_height())
        target = Gdk.Rectangle()
        target.x, target.y, target.width, target.height = int(ix * scale + ox), int(iy * scale + oy), 1, 1
        popover = Gtk.Popover(autohide=True)
        entry = Gtk.Entry(placeholder_text=_("Escribe y pulsa Enter"), width_chars=24)
        popover.set_child(entry)
        popover.set_parent(self.area)
        popover.set_pointing_to(target)
        color, width = self.color, self.width   # los de ahora, aunque luego cambien

        def accept(_entry):
            text = entry.get_text().strip()
            popover.popdown()
            if text:
                self._commit(ann.Text((ix, iy), text, color, width))
                self.area.queue_draw()

        entry.connect("activate", accept)
        popover.connect("closed", lambda p: GLib.idle_add(p.unparent))
        popover.popup()
        entry.grab_focus()

    # ------------------------------------------------------------- historial
    def _snapshot(self):
        return (self.pixbuf, list(self.anns))

    def _restore(self, state):
        pixbuf, anns = state
        if pixbuf is not self.pixbuf:
            self.pixbuf = pixbuf
            self.base = ann.surface_from_pixbuf(pixbuf)
        self.anns = list(anns)
        self.revision += 1
        self._set_selection(None)
        self._update_history_buttons()

    def _update_history_buttons(self):
        self.undo_btn.set_sensitive(bool(self.undo_stack))
        self.redo_btn.set_sensitive(bool(self.redo_stack))

    def _commit(self, annotation):
        self.undo_stack.append(self._snapshot())
        self.redo_stack.clear()
        self.anns.append(annotation)
        self.revision += 1
        self._update_history_buttons()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self._snapshot())
            self._restore(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self._snapshot())
            self._restore(self.redo_stack.pop())

    # --------------------------------------------------------------- recorte
    def _set_selection(self, sel):
        self.selection = sel
        self.crop_btn.set_visible(sel is not None and self.tool == "crop")
        self.area.queue_draw()

    def crop(self):
        if not self.selection:
            return
        x, y, w, h = (int(round(v)) for v in self.selection)
        w = min(w, self.pixbuf.get_width() - x)
        h = min(h, self.pixbuf.get_height() - y)
        if w < 1 or h < 1:
            return
        flat = self._flat()          # las anotaciones se integran en la imagen
        cropped = flat.new_subpixbuf(x, y, w, h).copy()
        self.undo_stack.append(self._snapshot())
        self.redo_stack.clear()
        self._restore((cropped, []))

    def open_preferences(self):
        self.get_application().show_preferences()

    # ------------------------------------------------------------------- OCR
    def ocr_all(self):
        self._run_ocr(self.pixbuf, psm=None)

    def ocr_region(self, sel):
        x, y, w, h = (int(round(v)) for v in sel)
        w = min(w, self.pixbuf.get_width() - x)
        h = min(h, self.pixbuf.get_height() - y)
        if w < 4 or h < 4:
            return
        # psm 6: bloque de texto uniforme, lo normal al seleccionar una zona
        self._run_ocr(self.pixbuf.new_subpixbuf(x, y, w, h).copy(), psm=6)

    def _run_ocr(self, pixbuf, psm):
        if not ocr.available():
            self._set_selection(None)
            dialog = Adw.AlertDialog(heading=_("Falta Tesseract"), body=ocr.install_hint())
            dialog.add_response("ok", _("Entendido"))
            dialog.present(self)
            return
        self.toasts.add_toast(Adw.Toast(title=_("Reconociendo texto…"), timeout=2))
        ocr.recognize_async(pixbuf, self._on_ocr_done, psm, self.cfg.get("ocr_langs"))

    def _on_ocr_done(self, text, error):
        self._set_selection(None)
        if error:
            self.toast(_("No se pudo reconocer el texto: {error}").format(error=error))
        elif not text:
            self.toast(_("No se encontró texto"))
        else:
            output.copy_text(text, self.get_display())
            toast = Adw.Toast(title=_("Texto copiado ({n} caracteres)").format(n=len(text)),
                              button_label=_("Ver"), timeout=6)
            toast.connect("button-clicked", lambda *_: self._show_text(text))
            self.toasts.add_toast(toast)

    def _show_text(self, text):
        dialog = Adw.Dialog(title=_("Texto reconocido"), content_width=520, content_height=380)
        view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=12, right_margin=12,
                            top_margin=10, bottom_margin=10)
        buffer = view.get_buffer()
        buffer.set_text(text)
        copy_btn = Gtk.Button(label=_("Copiar texto"), css_classes=["suggested-action"],
                              halign=Gtk.Align.CENTER, margin_top=8, margin_bottom=8)

        def copy(_btn):
            start, end = buffer.get_bounds()
            output.copy_text(buffer.get_text(start, end, False), self.get_display())
            copy_btn.set_label(_("¡Copiado!"))

        copy_btn.connect("clicked", copy)
        toolbar = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=view, vexpand=True))
        toolbar.add_top_bar(Adw.HeaderBar())
        toolbar.add_bottom_bar(copy_btn)
        dialog.set_child(toolbar)
        dialog.present(self)

    # ---------------------------------------------------------------- salida
    def _flat(self):
        return ann.flatten(self.pixbuf, self.anns)

    def copy(self):
        output.copy_pixbuf(self._flat(), self.get_display())
        self.copied_rev = self.revision
        self.toast(_("Copiado al portapapeles"))

    def save(self):
        try:
            path = output.save_pixbuf(self._flat(), self.cfg)
        except Exception as exc:  # noqa: BLE001 - mostrar cualquier fallo de E/S
            self.toast(_("No se pudo guardar: {error}").format(error=exc))
            return
        self.saved_rev = self.revision
        self.toast(_("Guardado en {path}").format(path=path))

    def finish(self):
        """Al cerrar, la versión editada se copia y guarda según las preferencias."""
        if not self.revision:
            return
        flat = self._flat()
        if self.cfg.get("auto_copy") and self.copied_rev != self.revision:
            output.copy_pixbuf(flat, self.get_display())
            self.copied_rev = self.revision
        if self.cfg.get("auto_save") and self.saved_rev != self.revision:
            try:
                output.save_pixbuf(flat, self.cfg)
                self.saved_rev = self.revision
            except OSError as exc:
                print(f"pickscreen: no se pudo guardar: {exc}")

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=3))
