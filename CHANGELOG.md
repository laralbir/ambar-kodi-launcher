# Changelog

Todos los cambios notables de este proyecto se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Added
- **Kodi/Spotify se deshabilitan solos en el home si no están
  disponibles**: nuevo `KodiGateway.is_reachable()` (`JSONRPC.Ping`) y
  `SpotifyGateway.is_configured()` (credenciales + token cacheado
  válido), expuestos vía `GET /api/library/kodi/status` y
  `GET /api/library/spotify/status`. El frontend comprueba ambos al
  cargar y cada 15s, y deshabilita la tarjeta de acceso y las pestañas
  correspondientes (`open-library-kodi`/`open-library-spotify`,
  pestañas "Artistas"/"Carpetas"/"CD"/"Listas") en vez de dejar entrar
  a una biblioteca que no va a devolver nada.
- **Spinner de carga en la carátula de "ahora suena"**: al cambiar de
  pista se muestra un indicador giratorio mientras la imagen se
  descarga, en vez de dejar el hueco en blanco hasta que termine de
  cargar (los listados de biblioteca ya tenían su propio `.loader`).
- **VU-metro estéreo con nivel real de audio** (un medidor por canal,
  L/R), configurable desde Ajustes entre dos estilos ("Barras LED" o
  "Aguja vintage"). El nivel se mide capturando de verdad la salida de
  audio del sistema (loopback), no es una animación decorativa:
  - Cada canal muestra su propia lectura en dB junto al medidor
    (leyenda numérica, ej. "-25 dB"; "-Inf dB" en silencio total, como
    en cualquier equipo de audio real — escala logarítmica).
  - Zonas de saturación (ámbar/rojo) dibujadas en la propia escala —
    arco de color en la aguja, segmentos con fondo tintado en las
    barras LED — no solo cuando el nivel las alcanza.
  - Si deja de recibirse audio (silencio prolongado, reproducción
    parada), el medidor cae de forma progresiva hasta el suelo
    (-60dB) en vez de quedarse congelado — vigilado también desde el
    frontend (`VU_IDLE_MS`/watchdog de decaimiento en `index.html`)
    como red de seguridad, independiente de si el backend sigue
    mandando eventos o no.
  - **macOS** (entorno de desarrollo): `ScreenCaptureKit` (macOS 13+),
    sin driver adicional — pide permiso de "Grabación de pantalla" la
    primera vez. El audio estéreo que entrega ScreenCaptureKit es
    *planar*, no intercalado (todo el canal 0 seguido de todo el canal
    1 en el mismo buffer, no muestras L/R alternadas) — verificado en
    vivo con el `AudioStreamBasicDescription`
    (`kAudioFormatFlagIsNonInterleaved`) antes de asumirlo. Verificado
    end-to-end con audio real (`say`), incluido el WebSocket hasta el
    navegador, con capturas de pantalla de ambos estilos.
    **Limitación conocida de macOS (no de la app):** al compilar con
    `python build.py` la app queda firmada de forma *ad-hoc* (sin
    certificado de Apple Developer). Esto puede provocar que la app no
    aparezca sola en Ajustes del Sistema → Privacidad y Seguridad →
    Grabación de pantalla (hay que añadirla a mano con "+"), y que el
    permiso se pierda en cada recompilación (firma distinta = macOS la
    trata como app nueva). Documentado en `README.md` y en la guía de
    usuario (`docs/index.html`). Arreglo definitivo pendiente: firmar
    con un certificado de código estable (ver `TODO.md`).
  - **Windows** (producción): captura WASAPI loopback vía el paquete
    `soundcard`, que ya entrega los canales separados
    (`(numframes, nchannels)`, sin mezclar). **Verificado en una VM
    Windows 11 ARM64 (UTM) con Python x64**: audio real reproducido
    dentro de la VM, medidor respondiendo correctamente — pendiente
    solo confirmarlo también en el mini PC real (Intel N100).
  - Si la captura no está disponible en la plataforma (import ausente,
    permiso denegado, error de cualquier tipo), el medidor
    simplemente queda inactivo — el resto de la app sigue funcionando
    con normalidad (`NullAudioLevelSource`).
  - Nuevas piezas: `ambar/domain/audio.py` (`LevelMeter`, conversión
    RMS→dBFS con ballística de integración ~300ms tipo VU analógico
    clásico — uno por canal), `ambar/ports/audio_level_source.py`
    (entrega una lista de fragmentos de muestras, una por canal),
    `ambar/adapters/audio/` (un adapter por plataforma),
    `ambar/application/audio_level.py` (`AudioLevelService`, un
    `LevelMeter` por canal, publica `AudioLevelChanged(db: list[float])`
    en el `EventBus` con limitación a ~20Hz). `SocketIOBridge` emite
    `audio_level` por WebSocket con `db` como lista.
  - Nota de implementación no obvia: la extracción de PCM del
    `CMSampleBuffer` de ScreenCaptureKit usa `CMBlockBufferCopyDataBytes`
    y no `CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer` —
    esta última tiene metadatos de bridging rotos en
    `pyobjc-framework-CoreMedia` 12.2.1 para su parámetro de salida
    `AudioBufferList` (rechaza `bytearray`/`ctypes`/`NSMutableData`/
    `objc.createStructType` con `ValueError("depythonifying 'pointer'...")`
    de forma consistente). Ver comentario en
    `ambar/adapters/audio/macos_screencapturekit.py`.
- **Exclusión mutua Kodi ↔ Spotify al reproducir**: al elegir reproducir
  una canción/álbum/carpeta/CD desde la biblioteca de Kodi se pausa
  automáticamente la reproducción de Spotify (Connect) si la había, y
  viceversa: al elegir reproducir una playlist de Spotify se para la
  reproducción activa en Kodi. Ambas llamadas son best-effort (no
  fallan si la otra fuente no está configurada o no responde) —
  `KodiGateway.stop()` y `SpotifyGateway.pause()` en
  `ambar/application/library.py`.

### Changed
- **Biblioteca de Kodi: pestaña "CD" separada de "Carpetas"**, activa
  solo cuando Kodi detecta de verdad un CD de audio (Redbook/CDDA)
  reproducible en la unidad (`system.hasmediadvdaudio` vía
  `XBMC.GetInfoBooleans`) — un disco de datos con FLAC/MP3 no cuenta,
  se navega como una fuente de archivos normal. Nuevo método
  `KodiGateway.has_audio_cd()` y ruta
  `GET /api/library/kodi/cd-available`.
  **En macOS esta detección no es fiable** (confirmado con `diskutil`:
  un CD de audio real, formato `CD_DA`, sigue dando
  `system.hasmediadvdaudio: false` en Kodi — límite conocido de los
  builds de Kodi para macOS, no de esta app), así que
  `LibraryService.kodi_cd_status()` añade un flag `detection_reliable`
  (`sys.platform != "darwin"`): en macOS la pestaña nunca se
  deshabilita y se muestra un aviso al entrar; en Windows/Linux se
  habilita/deshabilita según la detección real de Kodi, sin cambios de
  comportamiento respecto a lo anterior.
- `build.py`: el binario ya no lleva la versión en el nombre —
  siempre se llama `Ambar` (`Ambar.app`/`Ambar.exe`), para que cambie
  lo mínimo posible entre compilaciones (ayuda a que macOS no trate
  cada build como una app distinta a efectos de permisos). La versión
  se sigue escribiendo, pero solo en el manifest: `CFBundleShortVersionString`/
  `CFBundleVersion` en macOS (via `PlistBuddy` tras el build, porque
  PyInstaller no tiene flag de CLI para esto), recurso de versión
  (`--version-file`) en Windows.
- Refactor interno del backend a arquitectura hexagonal / DDD-lite /
  event-driven: `kiosk_server.py` (antes 417 líneas con todo mezclado)
  pasa a ser un entrypoint fino que arranca el composition root en
  `ambar/bootstrap.py`. El código se organiza en `ambar/domain`
  (`PlaybackState`, `PlaybackStateChanged`), `ambar/application`
  (`NowPlayingService`, `PlaybackControlService`, `LibraryService`,
  `SystemService`, `ConfigService`, y el `EventBus` interno),
  `ambar/ports` (`PlaybackSource`, `ConfigRepository`,
  `WindowController`) y `ambar/adapters` (`kodi/`, `spotify/`,
  `persistence/`, `web/`, `desktop/`). Los hilos de fondo de Kodi/
  Spotify ya no llaman a `socketio.emit(...)` directamente: publican
  `PlaybackStateChanged` en el `EventBus`, y `SocketIOBridge` es el
  único adapter que sabe que el transporte es WebSocket. Ninguna ruta,
  payload ni comportamiento observable cambia; verificado con
  `pytest` (nuevos tests de `NowPlayingService`) y comparando
  manualmente los endpoints antes/después.

### Removed
- Se elimina `eventlet` por completo (dependencia deprecada por sus
  propios autores) tras encontrar tres problemas distintos causados
  por ella en la misma sesión de trabajo — ver "Fixed" abajo. Flask-
  SocketIO pasa de `async_mode="eventlet"` a `async_mode="threading"`
  (con el paquete `simple-websocket` para mantener WebSockets reales,
  no solo long-polling). Los hilos de fondo de Kodi/Spotify usan
  `threading.Thread` normal en vez de `eventlet.spawn`, y
  `kiosk_server.py` ya no necesita `eventlet.monkey_patch()`.

### Fixed
- **Título "undefined" en el listado de álbumes de la biblioteca.**
  El frontend pedía el campo `title` para el título de la tarjeta,
  pero `AudioLibrary.GetAlbums` de Kodi no devuelve ese campo — el
  título real viene en `label` (igual que ya se usaba correctamente
  para artistas y canciones). Verificado contra la respuesta real de
  Kodi antes y después del fix.
- **La pestaña "CD" / carpetas no funcionaba nunca** (listado vacío
  siempre). Causa: `Files.GetDirectory` con
  `directory="sources://music/"` devuelve `Invalid params` en esta
  build de Kodi para *cualquier* combinación de `properties` (incluso
  ninguna) — un bug/limitación de Kodi específico de `media: "music"`
  con esa ruta virtual (con `media: "video"` sí funciona). Ahora se
  usa `Files.GetSources(media="music")` para el nivel raíz, que
  devuelve las fuentes reales configuradas y navega correctamente a
  partir de ahí. Verificado contra el JSON-RPC de Kodi directamente.
- **Carátulas de Kodi que no cargaban nunca** (`/api/art` devolvía 404).
  Causa: `KodiGateway.art_proxy` reenviaba a Kodi la URL `image://...`
  del thumbnail sin volver a codificarla — Flask ya la había
  decodificado una vez al leer el query param, así que Kodi recibía
  barras/dos-puntos sueltos en vez de un único segmento de path
  codificado, y no la resolvía. Verificado con una imagen real (JPEG
  640x640) cargando correctamente tras el fix.
- **"Ambar-x se ha cerrado inesperadamente" al salir de la app en
  macOS.** `SystemService.execute("exit")` cerraba la ventana pero
  nunca paraba `AudioLevelService`/`ScreenCaptureKitAudioSource` — el
  proceso de Python empezaba a finalizar mientras el stream de
  ScreenCaptureKit seguía disparando callbacks nativos de ObjC en un
  hilo de fondo, y el intérprete reventaba. Ahora `exit` para la
  captura de audio (con confirmación, hasta 5s) antes de cerrar la
  ventana. Verificado disparando la acción `exit` vía API con la
  ventana real activa, en dev y en el `.app` compilado — proceso
  terminado limpio, sin informe de crash en
  `~/Library/Logs/DiagnosticReports`.
- **VU-metro compilado sin captura de audio real** con el error
  `No module named 'CoreMedia'`: no era un problema de permisos ni de
  firma, sino que el venv usado para `python build.py` no tenía
  instaladas las dependencias nuevas de `requirements.txt`
  (`pyobjc-framework-ScreenCaptureKit`/`CoreMedia`) — sin ellas
  instaladas, `--collect-all` no encuentra nada que empaquetar y el
  `.app` arranca pero le falta el módulo. `build.py` ahora comprueba
  las dependencias de la plataforma *antes* de invocar a PyInstaller y
  para con un mensaje claro si falta algo, en vez de producir un
  binario que falla en silencio.
- **Pantalla en negro / launcher colgado al abrir la ventana en
  macOS.** Causa raíz: cuando `webview.start()` toma el hilo principal
  (bucle nativo de Cocoa vía PyObjC), acapara el GIL de tal forma que
  el hub de `eventlet` en el hilo de fondo deja de recibir tiempo de
  CPU — el socket del servidor queda escuchando pero nunca procesa
  peticiones, así que `index.html` nunca llega a cargar. Aislado con
  una reproducción mínima: un servidor con hilos nativos normales
  (sin eventlet) conviviendo con `webview.start()` funciona sin
  problema; el mismo servidor con eventlet se cuelga. Solucionado
  quitando eventlet (ver "Removed"). Verificado con la ventana real
  activa y peticiones HTTP/SocketIO en paralelo, y con capturas de
  pantalla del launcher renderizando correctamente.
- `eventlet==0.35.2` no soportaba Python 3.13 (faltaba el parche de
  `start_joinable_thread`), lo que rompía el arranque en macOS con un
  `AttributeError` durante `eventlet.monkey_patch()`. (Obsoleto: ver
  "Removed" — ya no se usa eventlet).
- `pywebview` requiere correr en el hilo principal en macOS
  (restricción de Cocoa/AppKit). El servidor se mueve a un hilo de
  fondo y `webview.start()` se queda en el hilo principal, evitando el
  `WebViewException: pywebview must be run on a main thread.`
- `build.py` usaba `--collect-all=dnspython` (nombre del paquete en
  PyPI) en vez de `--collect-all=dns` (nombre real del módulo
  importable), por lo que el `.app` compilado con PyInstaller fallaba
  al arrancar con `ModuleNotFoundError: No module named 'dns'`.
  (Obsoleto: ver "Removed" — `dnspython` era una dependencia transitiva
  de eventlet).
- **`python build.py` fallaba en Windows** con
  `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc1...` al
  generar el `.exe`. Causa: `write_windows_version_file()` escribía
  `_version_info.txt` con `open(..., "w")` sin `encoding="utf-8"`
  explícito; en macOS el encoding por defecto ya es UTF-8, pero en
  Windows usa la codificación del sistema (`cp1252` en Windows en
  español), que codifica la "Á" de "Ámbar" como el byte `0xC1` —
  inválido cuando PyInstaller relee el fichero forzando UTF-8.
  Detectado y corregido probando el build real en una VM Windows 11.

### Changed
- Documentación (`CLAUDE.md`, `.agents`, `docs/index.html`) ya no
  menciona el addon Chorus2 para la vista de biblioteca — quedó
  obsoleto desde que la navegación de artistas/álbumes/canciones/
  carpetas/CD se implementó de forma nativa contra la API JSON-RPC de
  Kodi, sin iframe ni webinterface externo.

## [0.1.0] - 2026-07-26

### Added
- Launcher táctil (`index.html`) con estética "receptor HiFi vintage"
  (gunmetal + ámbar VFD/LED), diseñado para pantalla panorámica baja
  1920x720.
- Servidor local `kiosk_server.py` (Flask + Flask-SocketIO) que
  unifica el estado de reproducción de Kodi (JSON-RPC/WebSocket) y
  Spotify (Spotipy) y expone `/api/now-playing`, `/api/control`,
  `/api/art`, `/login`, `/callback`.
- Vista de biblioteca nativa (artistas/álbumes/canciones de Kodi y
  playlists de Spotify) servida desde el propio backend.
- Modal de ajustes con persistencia en `config.json` (credenciales de
  Spotify, host/puerto de Kodi).
- Controles de sistema (pantalla completa, apagar, reiniciar, salir).
- Empaquetado con PyInstaller (`build.py` / `kiosk_server.spec`) hacia
  `.exe` (Windows) / `.app` (macOS) usando `pywebview` como ventana
  nativa sin bordes.
- Manual de usuario en `docs/`.

[Unreleased]: https://github.com/laralbir/ambar-kodi-launcher/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/laralbir/ambar-kodi-launcher/releases/tag/v0.1.0
