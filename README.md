# pickscreen

**🌐 [Español](#español) · [English](#english)**

---

## Español

Herramienta de capturas para Linux, al estilo Snagit: **captura, recorte, anotaciones, OCR y grabación de pantalla**.
Corre como servicio de usuario con atajos globales y un ícono en la bandeja.

### Características

- **Captura** de pantalla, ventana o región con el selector del escritorio.
- **Editor** con recorte, flechas, líneas, rectángulos, elipses, lápiz, resaltador, texto, números de paso y pixelado;
  deshacer/rehacer, color y grosor.
- **OCR**: copia al portapapeles el texto de una zona o de toda la imagen (Tesseract, español + inglés por defecto).
- **Grabación de pantalla** en WebM (con micrófono opcional) y exportación a **GIF**.
- **Atajos globales** y **ícono en la bandeja** con acceso rápido (se puede ocultar).
- **Copia y guardado automáticos** (PNG o JPG), configurables. Copiar, Guardar y OCR cierran el editor al terminar,
  y las ediciones sobrescriben el archivo del autoguardado en vez de crear un duplicado.
- Interfaz en **español e inglés**: usa el idioma del sistema y puedes cambiarlo en Preferencias.

### Cómo funciona

Usa **solo portales `xdg-desktop-portal`** (Screenshot, ScreenCast, GlobalShortcuts), sin APIs privadas de ningún
escritorio, para que funcione en cualquier Linux. Está hecho con Python 3 y GTK4/libadwaita (PyGObject), sin
dependencias de pip salvo Pillow (opcional, solo para exportar GIF).

> **Estado:** desarrollado y probado en Fedora 44, GNOME 50, Wayland y Python 3.14. En otras distros y escritorios
> debería funcionar por usar portales, pero **aún no está probado** (ver [Limitaciones](#limitaciones)).

### Requisitos

| Para | Paquetes (Fedora) | Notas |
|---|---|---|
| Base | `python3-gobject`, `gtk4`, `libadwaita` | libadwaita ≥ 1.5 |
| Portales | `xdg-desktop-portal` y el backend de tu escritorio | p. ej. `xdg-desktop-portal-gnome` |
| OCR | `tesseract`, `tesseract-langpack-spa` | Debian/Ubuntu: `tesseract-ocr tesseract-ocr-spa` · Arch: `tesseract tesseract-data-spa tesseract-data-eng` |
| Grabación | `gstreamer1-plugins-base`, `gstreamer1-plugins-good`, `pipewire-gstreamer` | Plugins: `pipewiresrc`, `vp8enc`, `webmmux` |
| GIF (opcional) | `python3-pillow` | |
| Portapapeles (opcional) | `wl-clipboard` | En Wayland |
| Bandeja en GNOME | `gnome-shell-extension-appindicator` | Hay que **activarla** y, si hace falta, cerrar sesión |

Los nombres de los paquetes cambian entre distros; esta tabla usa los de Fedora.

### Instalación

Se corre desde el código, sin empaquetar, y se instala solo para tu usuario (sin root):

```sh
git clone https://github.com/<tu-usuario>/pickscreen.git
cd pickscreen
python3 -m pickscreen install
```

Esto crea el lanzador `~/.local/bin/pickscreen`, el ícono, la entrada del menú de aplicaciones, el servicio D-Bus y
la unidad de systemd de usuario, y deja el servicio activo. Comprueba que `~/.local/bin` esté en tu `PATH`.

Tras cambiar el código, reinicia el servicio:

```sh
systemctl --user restart pickscreen
```

Para desinstalar: `pickscreen uninstall`.

### Uso

```text
pickscreen [capture]      captura y abre el editor
pickscreen ocr            elegir una zona y copiar su texto
pickscreen record         iniciar la grabación de pantalla (o detenerla)
pickscreen preferences    abrir las preferencias
pickscreen daemon         servicio en segundo plano (atajos globales)
pickscreen quit           cierra la instancia en ejecución

pickscreen install [--no-systemctl]   instala ícono, menú y servicio
pickscreen uninstall                  lo quita todo
pickscreen gnome-print on|off         usar la tecla Impr Pant con pickscreen (solo GNOME)
```

### Atajos de teclado

El servicio registra tres atajos globales mediante el portal GlobalShortcuts:

| Acción | Sugerido |
|---|---|
| Capturar pantalla | `Ctrl+Alt+P` |
| Copiar texto de una zona (OCR) | `Ctrl+Alt+O` |
| Grabar pantalla (iniciar/detener) | `Ctrl+Alt+R` |

Las teclas se cambian en la configuración de tu escritorio (en GNOME: *Configuración → Teclado → Atajos*). Si tu
escritorio no soporta GlobalShortcuts, asocia a mano los comandos `pickscreen capture`, `pickscreen ocr` y
`pickscreen record` a las teclas que prefieras. En **Preferencias → Atajos de teclado** puedes ver las asignadas.

### Configuración

Se abre desde el ícono de la bandeja, el botón de engranaje del editor, `Ctrl+,` o `pickscreen preferences`. Se guarda
en `~/.config/pickscreen/config.json`: carpeta y formato de guardado, copia/guardado automáticos, carpeta de vídeos,
micrófono, idioma del OCR, ícono de la bandeja e idioma de la interfaz.

Registros del servicio: `journalctl --user -u pickscreen -f`.

### Limitaciones

- La grabación ofrece pantalla completa o ventana; GNOME no permite elegir una región.
- En GNOME el ícono de la bandeja requiere la extensión AppIndicator.
- La grabación con micrófono (`video_audio`) aún no está probada.
- El servicio usa systemd; en distros sin systemd falta una alternativa de autostart.
- Cambiar el idioma de la interfaz requiere reiniciar pickscreen.
- La calidad del OCR puede variar con fondos oscuros o texto pequeño.

### Contribuir

Los comentarios del código y la documentación del proyecto están en español. Los textos de la interfaz se escriben
en español dentro de `_("...")` y su traducción al inglés va en el diccionario `EN` de `pickscreen/core/i18n.py`.

### Licencia

Pendiente de definir.

---

## English

A screenshot tool for Linux, Snagit-style: **capture, crop, annotations, OCR and screen recording**.
It runs as a user service with global shortcuts and a tray icon.

### Features

- **Capture** the screen, a window or a region using your desktop's own picker.
- **Editor** with crop, arrows, lines, rectangles, ellipses, pen, highlighter, text, step numbers and pixelate;
  undo/redo, color and thickness.
- **OCR**: copy the text of an area, or of the whole image, to the clipboard (Tesseract, Spanish + English by default).
- **Screen recording** to WebM (optional microphone) and export to **GIF**.
- **Global shortcuts** and a **tray icon** with quick access (it can be hidden).
- **Automatic copy and save** (PNG or JPG), configurable. Copy, Save and OCR close the editor when done, and edits
  overwrite the autosaved file instead of creating a duplicate.
- Interface in **Spanish and English**: it follows the system language and you can change it in Preferences.

### How it works

It uses **only `xdg-desktop-portal` portals** (Screenshot, ScreenCast, GlobalShortcuts), with no private desktop
APIs, so it can work on any Linux. It is built with Python 3 and GTK4/libadwaita (PyGObject), with no pip
dependencies except Pillow (optional, only for GIF export).

> **Status:** developed and tested on Fedora 44, GNOME 50, Wayland and Python 3.14. Other distros and desktops
> should work because it relies on portals, but they are **not tested yet** (see [Limitations](#limitations)).

### Requirements

| For | Packages (Fedora) | Notes |
|---|---|---|
| Base | `python3-gobject`, `gtk4`, `libadwaita` | libadwaita ≥ 1.5 |
| Portals | `xdg-desktop-portal` and your desktop's backend | e.g. `xdg-desktop-portal-gnome` |
| OCR | `tesseract`, `tesseract-langpack-spa` | Debian/Ubuntu: `tesseract-ocr tesseract-ocr-spa` · Arch: `tesseract tesseract-data-spa tesseract-data-eng` |
| Recording | `gstreamer1-plugins-base`, `gstreamer1-plugins-good`, `pipewire-gstreamer` | Plugins: `pipewiresrc`, `vp8enc`, `webmmux` |
| GIF (optional) | `python3-pillow` | |
| Clipboard (optional) | `wl-clipboard` | On Wayland |
| Tray on GNOME | `gnome-shell-extension-appindicator` | You must **enable** it and, if needed, log out and back in |

Package names differ between distros; this table uses Fedora's.

### Installation

It runs straight from the source, unpackaged, and installs for your user only (no root):

```sh
git clone https://github.com/<your-user>/pickscreen.git
cd pickscreen
python3 -m pickscreen install
```

This creates the `~/.local/bin/pickscreen` launcher, the icon, the application menu entry, the D-Bus service and
the systemd user unit, and starts the service. Make sure `~/.local/bin` is in your `PATH`.

After changing the code, restart the service:

```sh
systemctl --user restart pickscreen
```

To uninstall: `pickscreen uninstall`.

### Usage

```text
pickscreen [capture]      take a screenshot and open the editor
pickscreen ocr            pick an area and copy its text
pickscreen record         start screen recording (or stop it)
pickscreen preferences    open the preferences
pickscreen daemon         background service (global shortcuts)
pickscreen quit           close the running instance

pickscreen install [--no-systemctl]   install icon, menu entry and service
pickscreen uninstall                  remove everything
pickscreen gnome-print on|off         use the Print Screen key with pickscreen (GNOME only)
```

Note: the command-line help (`pickscreen help`) is currently in Spanish.

### Keyboard shortcuts

The service registers three global shortcuts through the GlobalShortcuts portal:

| Action | Suggested |
|---|---|
| Take screenshot | `Ctrl+Alt+P` |
| Copy text from an area (OCR) | `Ctrl+Alt+O` |
| Record screen (start/stop) | `Ctrl+Alt+R` |

Change the keys in your desktop settings (on GNOME: *Settings → Keyboard → Shortcuts*). If your desktop does not
support GlobalShortcuts, bind the `pickscreen capture`, `pickscreen ocr` and `pickscreen record` commands to the
keys you prefer. **Preferences → Keyboard shortcuts** shows the ones currently assigned.

### Configuration

Open it from the tray icon, the editor's gear button, `Ctrl+,` or `pickscreen preferences`. It is stored in
`~/.config/pickscreen/config.json`: save folder and format, automatic copy/save, video folder, microphone, OCR
language, tray icon and interface language.

Service logs: `journalctl --user -u pickscreen -f`.

### Limitations

- Recording offers full screen or a window; GNOME does not allow choosing a region.
- On GNOME the tray icon requires the AppIndicator extension.
- Recording with the microphone (`video_audio`) is not tested yet.
- The service relies on systemd; there is no autostart alternative yet for distros without it.
- Changing the interface language requires restarting pickscreen.
- OCR quality may vary with dark backgrounds or small text.

### Contributing

Code comments and project documentation are in Spanish. UI strings are written in Spanish inside `_("...")` and
their English translation goes in the `EN` dictionary of `pickscreen/core/i18n.py`.

### License

To be decided.
