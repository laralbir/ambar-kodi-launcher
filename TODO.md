# TODO — Ámbar

Lista de trabajo pendiente. Cuando se complete un punto, muévelo al
`CHANGELOG.md` (sección `[Unreleased]`) en vez de simplemente borrarlo
de aquí.

## Pendiente

- **VU-meter**: nivel real de audio, estéreo (L/R), configurable
  (barras LED / aguja vintage). Implementado y verificado en macOS;
  **la ruta Windows (WASAPI vía `soundcard`) sigue sin probar en
  hardware/VM Windows real** — validar en el mini PC antes de dar por
  cerrado.
- **Firma de código estable para el `.app` de macOS**: ahora mismo
  `build.py` firma en modo *ad-hoc* (`codesign_identity=None`), lo que
  hace que el permiso de "Grabación de pantalla" del VU-metro se
  pueda perder en cada recompilación y que la app no siempre aparezca
  sola en Ajustes del Sistema (hay que añadirla a mano). Firmar con un
  certificado de código local estable (o uno de Apple Developer)
  fijaría la identidad entre builds y evitaría tener que re-conceder
  el permiso cada vez. Documentado como limitación conocida en
  `README.md` y `docs/index.html` mientras tanto.
- Skins personalizadas cargables desde un directorio `/skins` +
  documentar en la guía de usuario (`docs/`) cómo crearlas.
- Barra lateral de volumen: subir/bajar/mute, con el % visible y
  sincronizado en tiempo real si el volumen cambia desde otro origen
  (teclado, mando/control remoto, control del propio SO) — no solo
  reflejar los cambios hechos desde el launcher.
- Selector de salida de audio del sistema (HDMI TV, analógico,
  óptico...), con el listado obtenido dinámicamente del sistema
  operativo.
- Configurar en qué pantalla/monitor arranca el launcher por defecto
  (relevante porque el mini PC saca a la vez a la pantalla táctil y a
  la TV).
- Permitir reproducir un álbum o artista completo desde la biblioteca
  de Kodi, no solo una canción suelta.
- Barra de progreso de reproducción seekable: permitir adelantar/
  atrasar la reproducción haciendo click en el punto deseado de la
  barra.
- Navegación de biblioteca consistente entre Kodi y Spotify
  (artistas/álbumes/playlists con la misma estructura de navegación
  en ambas fuentes).
- Conexión con Spotify más amigable:
  - Evitar el copy/paste manual de URLs para autorizar.
  - Wizard inicial de configuración si no hay `config.json` previo.
  - Poder relanzar ese wizard en cualquier momento desde Ajustes.

## Hecho recientemente (ver `CHANGELOG.md` para el detalle completo)

- Refactor a arquitectura hexagonal/DDD-lite/event-driven (`ambar/`).
- Fix de la pantalla en negro en macOS (eliminación de `eventlet`).
- Gestión de versiones y releases automáticas por GitHub Actions.
- VU-meter estéreo con nivel real de audio (macOS vía ScreenCaptureKit
  verificado; Windows vía WASAPI/`soundcard` pendiente de probar).
- Fix de las carátulas de Kodi que no cargaban (doble-decodificación
  de la URL `image://` al hacer de proxy hacia Kodi).
