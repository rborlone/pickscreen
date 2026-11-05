"""Íconos de herramientas dibujados con cairo.

Se dibujan con el color de texto del tema (`get_color()`), así se ven bien en
modo claro y oscuro sin depender de los íconos instalados en el sistema.
"""
import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def _ink(cr, fg, alpha=1.0):
    cr.set_source_rgba(fg[0], fg[1], fg[2], fg[3] * alpha)


# --- íconos en una rejilla lógica de 24x24 ---------------------------------
def _crop(cr, fg, _v):
    cr.move_to(7, 3); cr.line_to(7, 17); cr.line_to(21, 17)
    cr.move_to(3, 7); cr.line_to(17, 7); cr.line_to(17, 21)
    cr.stroke()


def _arrow(cr, fg, _v):
    cr.move_to(5, 19); cr.line_to(18, 6)
    cr.move_to(9.5, 6); cr.line_to(18, 6); cr.line_to(18, 14.5)
    cr.stroke()


def _line(cr, fg, _v):
    cr.move_to(5, 19); cr.line_to(19, 5)
    cr.stroke()


def _rect(cr, fg, _v):
    cr.rectangle(4, 6, 16, 12)
    cr.stroke()


def _ellipse(cr, fg, _v):
    cr.save()
    cr.translate(12, 12)
    cr.scale(9, 7)
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.restore()        # el trazo se mide ya sin la escala
    cr.stroke()


def _pen(cr, fg, _v):
    cr.move_to(4, 20); cr.line_to(5.2, 15); cr.line_to(16, 4.2)
    cr.line_to(19.8, 8); cr.line_to(9, 18.8); cr.close_path()
    cr.stroke()
    cr.move_to(13.5, 6.8); cr.line_to(17.2, 10.5)
    cr.stroke()


def _highlight(cr, fg, _v):
    _ink(cr, fg, 0.45)
    cr.set_line_width(7)
    cr.set_line_cap(cairo.LINE_CAP_BUTT)
    cr.move_to(7, 15); cr.line_to(15, 7)
    cr.stroke()
    _ink(cr, fg)
    cr.set_line_width(1.8)
    cr.move_to(4, 21); cr.line_to(20, 21)
    cr.stroke()


def _text(cr, fg, _v):
    cr.move_to(6, 6.5); cr.line_to(18, 6.5)
    cr.move_to(12, 6.5); cr.line_to(12, 19)
    cr.move_to(9, 19); cr.line_to(15, 19)
    cr.stroke()


def _step(cr, fg, _v):
    cr.arc(12, 12, 9, 0, 2 * math.pi)
    cr.stroke()
    cr.move_to(10, 10); cr.line_to(12.5, 8); cr.line_to(12.5, 16.5)
    cr.stroke()


def _pixelate(cr, fg, _v):
    size, start = 5, 4.5
    for i in range(3):
        for j in range(3):
            _ink(cr, fg, 1.0 if (i + j) % 2 == 0 else 0.3)
            cr.rectangle(start + i * size, start + j * size, size, size)
            cr.fill()


def _ocr(cr, fg, _v):
    # esquinas de «escaneo» con una T dentro
    cr.move_to(3, 8); cr.line_to(3, 3); cr.line_to(8, 3)
    cr.move_to(16, 3); cr.line_to(21, 3); cr.line_to(21, 8)
    cr.move_to(21, 16); cr.line_to(21, 21); cr.line_to(16, 21)
    cr.move_to(8, 21); cr.line_to(3, 21); cr.line_to(3, 16)
    cr.move_to(8.5, 9); cr.line_to(15.5, 9)
    cr.move_to(12, 9); cr.line_to(12, 15.5)
    cr.stroke()


_ICONS = {
    "ocr": _ocr,
    "crop": _crop, "arrow": _arrow, "line": _line, "rect": _rect,
    "ellipse": _ellipse, "pen": _pen, "highlight": _highlight,
    "text": _text, "step": _step, "pixelate": _pixelate,
}


# --- elementos con tamaño propio (en píxeles) ------------------------------
def _swatch(cr, w, h, fg, color):
    radius = min(w, h) / 2 - 2
    cr.arc(w / 2, h / 2, radius, 0, 2 * math.pi)
    cr.set_source_rgba(*color)
    cr.fill_preserve()
    _ink(cr, fg, 0.35)              # borde fino para que se vea el blanco
    cr.set_line_width(1)
    cr.stroke()


def _line_width(cr, w, h, fg, value):
    _ink(cr, fg)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_width(min(max(value or 1, 1), 14))
    cr.move_to(7, h / 2)
    cr.line_to(w - 7, h / 2)
    cr.stroke()


def render(cr, kind, w, h, value, fg) -> None:
    """Dibuja el glifo `kind` en un lienzo de w x h. `fg` es (r, g, b, a)."""
    if kind == "swatch":
        _swatch(cr, w, h, fg, value)
    elif kind == "linew":
        _line_width(cr, w, h, fg, value)
    else:
        scale = min(w, h) / 24
        cr.translate((w - 24 * scale) / 2, (h - 24 * scale) / 2)
        cr.scale(scale, scale)
        _ink(cr, fg)
        cr.set_line_width(1.8)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        _ICONS[kind](cr, fg, value)


class Glyph(Gtk.DrawingArea):
    def __init__(self, kind, value=None, width=20, height=20):
        super().__init__(content_width=width, content_height=height,
                         halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.kind = kind
        self.value = value
        self.set_draw_func(self._draw)

    def set_kind(self, kind):
        self.kind = kind
        self.queue_draw()

    def set_value(self, value):
        self.value = value
        self.queue_draw()

    def _draw(self, _area, cr, w, h):
        c = self.get_color()
        render(cr, self.kind, w, h, self.value, (c.red, c.green, c.blue, c.alpha))
