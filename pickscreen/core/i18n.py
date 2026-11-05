"""Traducciones de la interfaz (español base + inglés), sin dependencias.

Las cadenas en español son la clave: `_("Guardar")` devuelve "Save" si el idioma es inglés.
Una cadena sin traducción se muestra en español. Para los textos con variables se usan
marcadores con nombre: `_("Guardado en {path}").format(path=...)`.

El idioma sale de `language` en la configuración ("es", "en" o None = el del sistema) y se
fija al importar el módulo; cambiarlo en Preferencias requiere reiniciar pickscreen.
"""
import json
import os
from pathlib import Path

LANGUAGES = {"es": "Español", "en": "English"}


def _configured():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    try:
        return json.loads((Path(base) / "pickscreen" / "config.json").read_text()).get("language")
    except (OSError, ValueError, AttributeError):
        return None


def detect(configured=None):
    """Idioma a usar: el configurado o, si no hay, el del sistema (español si empieza por «es»)."""
    if configured in LANGUAGES:
        return configured
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(var, "")
        if value and value != "C":
            return "es" if value.lower().startswith("es") else "en"
    return "es"


EN = {
    # --- editor ---
    "Recorte": "Crop", "Flecha": "Arrow", "Línea": "Line", "Rectángulo": "Rectangle",
    "Elipse": "Ellipse", "Lápiz": "Pen", "Resaltador": "Highlighter", "Texto": "Text",
    "Número de paso": "Step number", "Pixelar": "Pixelate",
    "Copiar texto de una zona (OCR)": "Copy text from an area (OCR)",
    "Nueva captura": "New capture",
    "Deshacer (Ctrl+Z)": "Undo (Ctrl+Z)",
    "Rehacer (Ctrl+Shift+Z)": "Redo (Ctrl+Shift+Z)",
    "Guardar": "Save", "Guardar archivo (Ctrl+S)": "Save file (Ctrl+S)",
    "Copiar": "Copy", "Copiar al portapapeles (Ctrl+C)": "Copy to clipboard (Ctrl+C)",
    "Copiar todo el texto de la imagen (OCR)": "Copy all text in the image (OCR)",
    "Preferencias (Ctrl+,)": "Preferences (Ctrl+,)",
    "Aplicar recorte": "Apply crop",
    "Más herramientas": "More tools",
    "Personalizado…": "Custom…", "Color": "Color", "Grosor": "Thickness",
    "Escribe y pulsa Enter": "Type and press Enter",
    "Falta Tesseract": "Tesseract is missing", "Entendido": "Got it",
    "Reconociendo texto…": "Recognizing text…",
    "No se pudo reconocer el texto: {error}": "Could not recognize the text: {error}",
    "No se encontró texto": "No text found",
    "Texto copiado ({n} caracteres)": "Text copied ({n} characters)",
    "Ver": "View", "Texto reconocido": "Recognized text", "Copiar texto": "Copy text",
    "¡Copiado!": "Copied!", "Copiado al portapapeles": "Copied to clipboard",
    "No se pudo guardar: {error}": "Could not save: {error}",
    "Guardado en {path}": "Saved to {path}",
    # --- bandeja ---
    "Capturar pantalla": "Take screenshot", "Grabar pantalla": "Record screen",
    "Detener grabación": "Stop recording", "Preferencias…": "Preferences…", "Salir": "Quit",
    # --- ventana de grabación ---
    "Grabando…": "Recording…", "Detener": "Stop", "Abrir": "Open", "Carpeta": "Folder",
    "Exportar GIF": "Export GIF",
    "Instala Pillow (python3-pillow) para exportar GIF": "Install Pillow (python3-pillow) to export GIF",
    "Grabación guardada": "Recording saved", "No se pudo grabar": "Could not record",
    "No se generó ningún archivo.": "No file was generated.",
    "Creando GIF…": "Creating GIF…", "GIF creado": "GIF created",
    "No se pudo crear el GIF": "Could not create the GIF",
    # --- captura / grabación / OCR / GIF (mensajes de error) ---
    "No se pudo contactar al portal: {error}": "Could not reach the portal: {error}",
    "El visor se cerró sin devolver una imagen (¿se canceló la captura?).":
        "The viewer closed without returning an image (was the capture cancelled?).",
    "El portal no pudo completar la captura (código {code}, resultados: {results}).":
        "The portal could not complete the capture (code {code}, results: {results}).",
    "Faltan plugins de GStreamer: {plugins}": "Missing GStreamer plugins: {plugins}",
    "No se pudo abrir PipeWire: {error}": "Could not open PipeWire: {error}",
    "No se pudo preparar la grabación: {error}": "Could not prepare the recording: {error}",
    "El portal no pudo {step} ({detail}).": "The portal could not {step} ({detail}).",
    "crear la sesión": "create the session", "elegir la fuente": "choose the source",
    "iniciar la captura": "start the capture", "código {code}": "code {code}",
    "El archivo no tiene vídeo.": "The file has no video.",
    "No se pudo leer ningún fotograma.": "Could not read any frame.",
    "Tesseract no está instalado. Instálalo con:": "Tesseract is not installed. Install it with:",
    "Tesseract no tiene ningún idioma instalado.": "Tesseract has no language installed.",
    "No se pudo preparar la imagen.": "Could not prepare the image.",
    "El reconocimiento tardó demasiado.": "Recognition took too long.",
    "Tesseract falló.": "Tesseract failed.",
    # --- app / notificaciones ---
    "No se pudo reconocer el texto": "Could not recognize the text",
    "Prueba con otra zona.": "Try another area.",
    # --- atajos ---
    "Grabar pantalla (iniciar/detener)": "Record screen (start/stop)",
    # --- preferencias ---
    "Preferencias": "Preferences", "Capturas": "Screenshots",
    "Carpeta de guardado": "Save folder", "Elegir…": "Choose…",
    "Volver a la carpeta por defecto": "Back to the default folder",
    "Guardar automáticamente": "Save automatically",
    "Cada captura se guarda como archivo.": "Every capture is saved as a file.",
    "Copiar automáticamente": "Copy automatically",
    "Cada captura queda en el portapapeles.": "Every capture is placed on the clipboard.",
    "Formato de imagen": "Image format", "Calidad del JPG": "JPG quality",
    "Grabación de pantalla": "Screen recording", "Carpeta de vídeos": "Video folder",
    "Grabar micrófono": "Record microphone",
    "Añade el audio del micrófono al vídeo.": "Adds the microphone audio to the video.",
    "Reconocimiento de texto (OCR)": "Text recognition (OCR)",
    "Automático (español + inglés)": "Automatic (Spanish + English)",
    "Idioma del texto": "Text language", "Tesseract no está instalado": "Tesseract is not installed",
    "Idiomas instalados en Tesseract": "Languages installed in Tesseract",
    "Español": "Spanish", "Inglés": "English", "Portugués": "Portuguese", "Francés": "French",
    "Alemán": "German", "Italiano": "Italian", "Catalán": "Catalan",
    "Atajos de teclado": "Keyboard shortcuts",
    "Se cambian en la configuración del escritorio (en GNOME: Configuración → Teclado → Atajos). "
    "También puedes asociar el comando de cada fila a una tecla.":
        "Change them in your desktop settings (in GNOME: Settings → Keyboard → Shortcuts). "
        "You can also bind each row's command to a key.",
    "Sin asignar": "Not assigned", "General": "General",
    "Mostrar ícono en la bandeja": "Show tray icon",
    "Ícono en la barra superior con acceso rápido. En GNOME requiere la extensión AppIndicator.":
        "Icon in the top bar with quick access. On GNOME it needs the AppIndicator extension.",
    "Idioma de la interfaz": "Interface language",
    "Automático (idioma del sistema: {lang})": "Automatic (system language: {lang})",
    "Reinicia pickscreen para aplicar el idioma.": "Restart pickscreen to apply the language.",
    "Reiniciar": "Restart",
}


class _Translator:
    def __init__(self):
        self.lang = detect(_configured())

    def __call__(self, text):
        return EN.get(text, text) if self.lang == "en" else text


_ = _Translator()


def language():
    return _.lang


def system_language():
    """Idioma que se usaría sin ninguna preferencia guardada."""
    return detect(None)
