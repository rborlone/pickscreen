"""Exportar un vídeo a GIF animado (GStreamer decodifica, Pillow codifica)."""
import threading
from pathlib import Path

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstPbutils", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import GLib, Gst, GstApp, GstPbutils  # noqa: F401
from .i18n import _

Gst.init(None)


def available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def export_async(video: Path, callback, progress=None, width=720, fps=10):
    """Convierte en un hilo. `callback(path, error)` y `progress(0..1)` corren en el hilo principal."""
    def work():
        try:
            out = _export(Path(video), width, fps,
                          lambda f: progress and GLib.idle_add(progress, f))
            GLib.idle_add(callback, out, None)
        except Exception as exc:  # noqa: BLE001
            GLib.idle_add(callback, None, str(exc))
    threading.Thread(target=work, daemon=True).start()


def _export(video: Path, width: int, fps: int, report) -> Path:
    from PIL import Image

    info = GstPbutils.Discoverer.new(10 * Gst.SECOND).discover_uri(video.resolve().as_uri())
    streams = info.get_video_streams()
    if not streams:
        raise RuntimeError(_("El archivo no tiene vídeo."))
    w, h = streams[0].get_width(), streams[0].get_height()
    duration = max(info.get_duration(), 1)
    out_w = min(width, w) // 2 * 2
    out_h = max(2, round(h * out_w / w)) // 2 * 2

    pipeline = Gst.parse_launch(
        f'uridecodebin uri="{video.resolve().as_uri()}" ! videoconvert ! videoscale ! videorate '
        f"! video/x-raw,format=RGB,width={out_w},height={out_h},framerate={fps}/1 "
        "! appsink name=sink sync=false max-buffers=4 drop=false")
    sink = pipeline.get_by_name("sink")
    pipeline.set_state(Gst.State.PLAYING)
    frames = []
    try:
        while True:
            sample = sink.try_pull_sample(10 * Gst.SECOND)
            if sample is None:
                break
            buf = sample.get_buffer()
            ok, mapped = buf.map(Gst.MapFlags.READ)
            if not ok:
                continue
            try:
                image = Image.frombytes("RGB", (out_w, out_h), bytes(mapped.data))
            finally:
                buf.unmap(mapped)
            frames.append(image.quantize(colors=128, method=Image.Quantize.FASTOCTREE))
            if buf.pts != Gst.CLOCK_TIME_NONE:
                report(min(buf.pts / duration, 1.0))
    finally:
        pipeline.set_state(Gst.State.NULL)
    if not frames:
        raise RuntimeError(_("No se pudo leer ningún fotograma."))
    out = video.with_suffix(".gif")
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=1000 // fps,
                   loop=0, optimize=False, disposal=1)
    return out
