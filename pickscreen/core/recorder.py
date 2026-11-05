"""Grabación de pantalla: portal ScreenCast (PipeWire) + GStreamer → WebM (VP8/Opus).

El portal pide al usuario qué pantalla o ventana grabar (en GNOME muestra su
propio selector). Funciona igual en Wayland y X11 en cualquier escritorio con
xdg-desktop-portal.
"""
import os
import time
from pathlib import Path

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gio, GLib, Gst

from . import config, portal
from .i18n import _

Gst.init(None)
IFACE = "org.freedesktop.portal.ScreenCast"
SESSION_IFACE = "org.freedesktop.portal.Session"


def missing_plugins(audio: bool) -> list:
    needed = ["pipewiresrc", "videoconvert", "videorate", "vp8enc", "webmmux", "filesink"]
    if audio:
        needed += ["pulsesrc", "opusenc", "audioconvert"]
    return [n for n in needed if Gst.ElementFactory.find(n) is None]


class Recorder:
    """Una grabación. `on_started(path)`, `on_finished(path, error)`; ambos en el hilo principal."""

    def __init__(self, cfg, on_started, on_finished):
        self.cfg = cfg
        self.on_started = on_started
        self.on_finished = on_finished
        self.conn = None
        self.session = None
        self.pipeline = None
        self.path = None
        self.recording = False
        self._stopping = False
        self._closed_sub = None
        self._fail_timer = None

    # ------------------------------------------------------------ portal
    def start(self):
        audio = bool(self.cfg.get("video_audio"))
        missing = missing_plugins(audio)
        if missing:
            return self._fail(_("Faltan plugins de GStreamer: {plugins}").format(plugins=", ".join(missing)))
        self.conn = portal.connection()
        portal.request(IFACE, "CreateSession",
                       lambda t: GLib.Variant("(a{sv})", ({
                           "handle_token": GLib.Variant("s", t),
                           "session_handle_token": GLib.Variant("s", portal.new_token("pickscreen_cast")),
                       },)),
                       self._on_session)

    def _on_session(self, code, results):
        if code != 0:
            return self._fail(self._why(code, results, _("crear la sesión")))
        self.session = results["session_handle"]
        self._closed_sub = self.conn.signal_subscribe(
            portal.BUS_NAME, SESSION_IFACE, "Closed", self.session, None,
            Gio.DBusSignalFlags.NONE, lambda *_a: GLib.idle_add(self._session_closed))
        portal.request(IFACE, "SelectSources",
                       lambda t: GLib.Variant("(oa{sv})", (self.session, {
                           "handle_token": GLib.Variant("s", t),
                           "types": GLib.Variant("u", 3),          # pantalla | ventana
                           "multiple": GLib.Variant("b", False),
                           "cursor_mode": GLib.Variant("u", 2),    # puntero dentro del vídeo
                       })),
                       self._on_selected)

    def _on_selected(self, code, results):
        if code != 0:
            return self._fail(self._why(code, results, _("elegir la fuente")))
        portal.request(IFACE, "Start",
                       lambda t: GLib.Variant("(osa{sv})", (self.session, "", {
                           "handle_token": GLib.Variant("s", t)})),
                       self._on_portal_started)

    def _on_portal_started(self, code, results):
        if code == 1:
            return self._fail(None)                  # el usuario canceló el selector
        if code != 0 or not results.get("streams"):
            return self._fail(self._why(code, results, _("iniciar la captura")))
        node_id = results["streams"][0][0]
        self.conn.call_with_unix_fd_list(
            portal.BUS_NAME, portal.OBJ_PATH, IFACE, "OpenPipeWireRemote",
            GLib.Variant("(oa{sv})", (self.session, {})), GLib.VariantType("(h)"),
            Gio.DBusCallFlags.NONE, -1, None, None, self._on_fd, node_id)

    def _on_fd(self, conn, result, node_id):
        try:
            reply, fds = conn.call_with_unix_fd_list_finish(result)
            fd = fds.get(reply.unpack()[0])
        except GLib.Error as exc:
            return self._fail(_("No se pudo abrir PipeWire: {error}").format(error=exc.message))
        self._start_pipeline(fd, node_id)

    # --------------------------------------------------------- GStreamer
    def _output_path(self) -> Path:
        folder = config.video_dir(self.cfg)
        folder.mkdir(parents=True, exist_ok=True)
        base = time.strftime("pickscreen_%Y-%m-%d_%H-%M-%S")
        path, n = folder / f"{base}.webm", 1
        while path.exists():
            path, n = folder / f"{base}_{n}.webm", n + 1
        return path

    def _start_pipeline(self, fd, node_id):
        fps = int(self.cfg.get("video_fps", 30))
        desc = (
            f"pipewiresrc fd={fd} path={node_id} do-timestamp=true ! queue max-size-buffers=8 leaky=downstream "
            f"! videoconvert ! videorate ! video/x-raw,framerate={fps}/1 "
            "! vp8enc deadline=1 cpu-used=6 threads=4 min-quantizer=4 max-quantizer=24 keyframe-max-dist=90 "
            "! queue ! mux. "
            "webmmux name=mux ! filesink name=out"
        )
        if self.cfg.get("video_audio"):
            desc += (" pulsesrc do-timestamp=true ! queue ! audioconvert ! audioresample "
                     "! opusenc ! queue ! mux.")
        try:
            self.pipeline = Gst.parse_launch(desc)
            self.path = self._output_path()
            self.pipeline.get_by_name("out").set_property("location", str(self.path))
        except (GLib.Error, OSError) as exc:
            os.close(fd)
            return self._fail(_("No se pudo preparar la grabación: {error}").format(error=exc))
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.recording = True
        self.on_started(self.path)

    def _on_bus(self, _bus, message):
        if message.type == Gst.MessageType.EOS:
            self._finish(None)
        elif message.type == Gst.MessageType.ERROR:
            err, _dbg = message.parse_error()
            self._finish(err.message)

    # -------------------------------------------------------------- parar
    def stop(self):
        if self._stopping or not self.recording:
            return
        self._stopping = True
        self.pipeline.send_event(Gst.Event.new_eos())    # cierra el archivo con índice y duración
        self._fail_timer = GLib.timeout_add_seconds(5, lambda: (self._finish(None), False)[1])

    def _session_closed(self):
        # El usuario detuvo la grabación desde el escritorio (indicador de GNOME).
        self.session = None
        if self.recording:
            self.stop()
        return False

    def _finish(self, error):
        if not self.recording:
            return
        self.recording = False
        if self._fail_timer:
            GLib.source_remove(self._fail_timer)
            self._fail_timer = None
        self.pipeline.get_bus().remove_signal_watch()
        self.pipeline.set_state(Gst.State.NULL)
        self._close_session()
        path = self.path if self.path and self.path.exists() and self.path.stat().st_size > 0 else None
        self.on_finished(path, error)

    def _close_session(self):
        if self._closed_sub is not None:
            self.conn.signal_unsubscribe(self._closed_sub)
            self._closed_sub = None
        if self.session:
            self.conn.call(portal.BUS_NAME, self.session, SESSION_IFACE, "Close", None, None,
                           Gio.DBusCallFlags.NONE, -1, None, None)
            self.session = None

    def _fail(self, message):
        self._close_session()
        self.on_finished(None, message)

    @staticmethod
    def _why(code, results, step):
        detail = results.get("error") if code is None else _("código {code}").format(code=code)
        return _("El portal no pudo {step} ({detail}).").format(step=step, detail=detail)
