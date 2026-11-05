"""Anotaciones como objetos y su dibujo con cairo.

Las anotaciones usan coordenadas de la imagen. El mismo `draw()` sirve para
pintar en pantalla y para aplanar la imagen al copiar o guardar.
"""
import math
from dataclasses import dataclass, field

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, Pango, PangoCairo

Color = tuple  # (r, g, b, a) con valores de 0 a 1


@dataclass
class Shape:
    kind: str            # "line" | "arrow" | "rect" | "ellipse"
    p0: tuple
    p1: tuple
    color: Color
    width: float


@dataclass
class Stroke:
    points: list = field(default_factory=list)
    color: Color = (1, 0, 0, 1)
    width: float = 4
    highlight: bool = False


@dataclass
class Text:
    pos: tuple
    text: str
    color: Color
    width: float


@dataclass
class Step:
    pos: tuple
    number: int
    color: Color
    width: float


@dataclass
class Pixelate:
    rect: tuple          # (x, y, w, h)
    block: int = 8


def surface_from_pixbuf(pixbuf) -> cairo.ImageSurface:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, pixbuf.get_width(), pixbuf.get_height())
    cr = cairo.Context(surface)
    Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.paint()
    return surface


def draw(cr, ann, base) -> None:
    """Dibuja una anotación. `base` es la imagen original (surface cairo)."""
    cr.save()
    if isinstance(ann, Shape):
        _draw_shape(cr, ann)
    elif isinstance(ann, Stroke):
        _draw_stroke(cr, ann)
    elif isinstance(ann, Text):
        _draw_text(cr, ann)
    elif isinstance(ann, Step):
        _draw_step(cr, ann)
    elif isinstance(ann, Pixelate):
        _draw_pixelate(cr, ann, base)
    cr.restore()


def flatten(pixbuf, annotations):
    """Devuelve un pixbuf con las anotaciones pintadas sobre la imagen."""
    if not annotations:
        return pixbuf
    w, h = pixbuf.get_width(), pixbuf.get_height()
    base = surface_from_pixbuf(pixbuf)
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(out)
    cr.set_source_surface(base, 0, 0)
    cr.paint()
    for ann in annotations:
        draw(cr, ann, base)
    return Gdk.pixbuf_get_from_surface(out, 0, 0, w, h)


# ----------------------------------------------------------------- formas
def _draw_shape(cr, s: Shape) -> None:
    (x0, y0), (x1, y1) = s.p0, s.p1
    cr.set_source_rgba(*s.color)
    cr.set_line_width(s.width)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)

    if s.kind == "line":
        cr.move_to(x0, y0)
        cr.line_to(x1, y1)
        cr.stroke()
    elif s.kind == "arrow":
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length < 1:
            return
        head = min(10 + s.width * 3, length)
        angle = math.atan2(dy, dx)
        # la línea termina dentro de la punta para que no sobresalga
        cr.move_to(x0, y0)
        cr.line_to(x1 - math.cos(angle) * head * 0.6, y1 - math.sin(angle) * head * 0.6)
        cr.stroke()
        cr.move_to(x1, y1)
        for side in (-0.45, 0.45):
            cr.line_to(x1 - head * math.cos(angle + side), y1 - head * math.sin(angle + side))
        cr.close_path()
        cr.fill()
    elif s.kind == "rect":
        cr.rectangle(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
        cr.stroke()
    elif s.kind == "ellipse":
        rx, ry = abs(x1 - x0) / 2, abs(y1 - y0) / 2
        if rx < 0.5 or ry < 0.5:
            return
        # La escala solo se aplica al construir el trazado; al restaurar, el
        # grosor se mide en unidades normales y no se deforma.
        cr.save()
        cr.translate((x0 + x1) / 2, (y0 + y1) / 2)
        cr.scale(rx, ry)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.stroke()


def _draw_stroke(cr, s: Stroke) -> None:
    if not s.points:
        return
    r, g, b, a = s.color
    if s.highlight:
        cr.set_source_rgba(r, g, b, 0.4)
        cr.set_line_width(s.width * 4)
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
    else:
        cr.set_source_rgba(r, g, b, a)
        cr.set_line_width(s.width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.move_to(*s.points[0])
    for p in s.points[1:]:
        cr.line_to(*p)
    if len(s.points) == 1:
        cr.line_to(s.points[0][0] + 0.01, s.points[0][1])  # un clic = un punto
    cr.stroke()


# ------------------------------------------------------------------ texto
def _layout(cr, text, size):
    layout = PangoCairo.create_layout(cr)
    font = Pango.FontDescription()
    font.set_family("Sans")
    font.set_weight(Pango.Weight.BOLD)
    font.set_absolute_size(size * Pango.SCALE)
    layout.set_font_description(font)
    layout.set_text(text, -1)
    return layout


def _draw_text(cr, t: Text) -> None:
    layout = _layout(cr, t.text, 12 + t.width * 4)
    cr.set_source_rgba(*t.color)
    cr.move_to(*t.pos)
    PangoCairo.show_layout(cr, layout)


def _draw_step(cr, s: Step) -> None:
    radius = 10 + s.width * 2
    x, y = s.pos
    cr.set_source_rgba(*s.color)
    cr.arc(x, y, radius, 0, 2 * math.pi)
    cr.fill()
    r, g, b, _a = s.color
    dark_text = (0.299 * r + 0.587 * g + 0.114 * b) > 0.6
    cr.set_source_rgba(*((0, 0, 0, 1) if dark_text else (1, 1, 1, 1)))
    layout = _layout(cr, str(s.number), radius * 1.2)
    tw, th = layout.get_pixel_size()
    cr.move_to(x - tw / 2, y - th / 2)
    PangoCairo.show_layout(cr, layout)


# --------------------------------------------------------------- pixelado
def _draw_pixelate(cr, p: Pixelate, base) -> None:
    x, y, w, h = p.rect
    if w < 1 or h < 1:
        return
    b = max(2, p.block)
    # 1) reducir la zona a una miniatura; 2) ampliarla sin suavizar.
    small = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, math.ceil(w / b)), max(1, math.ceil(h / b)))
    sc = cairo.Context(small)
    sc.scale(1 / b, 1 / b)
    sc.set_source_surface(base, -x, -y)
    sc.get_source().set_filter(cairo.FILTER_GOOD)
    sc.paint()

    cr.rectangle(x, y, w, h)
    cr.clip()
    cr.translate(x, y)
    cr.scale(b, b)
    cr.set_source_surface(small, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_NEAREST)
    cr.paint()
