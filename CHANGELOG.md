# Changelog

Todos los cambios notables de este proyecto se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Added
- **Controles de volumen integrados directamente en el home**, en vez
  de una vista aparte que había que abrir con un icono 🔊 (`#view-volume`,
  ya retirada): fila compacta bajo el transporte con
  silenciar/−5/slider/+5/porcentaje, siempre visible. Se sondea el
  volumen real cada 2s de forma continua (antes solo mientras la vista
  aparte estaba abierta).
- **VU-metro en pantalla completa**: icono ⛶ junto al medidor lo
  amplía a pantalla completa (barras LED o aguja, según el estilo
  elegido), para verlo bien desde lejos. Los mismos elementos del DOM
  se mueven al overlay y de vuelta (no se duplican), así que
  `updateVuMeter()` sigue funcionando igual sin cambios.
- **La pantalla ya no se apaga ni salta el salvapantallas mientras
  Ámbar está en ejecución** (relevante para un kiosko que se supone
  siempre visible). Nuevo puerto `ScreenWakeLock` con un adapter por
  plataforma (`ambar/adapters/desktop/`): `MacWakeLock` (lanza
  `caffeinate -d -i` como proceso auxiliar, ya viene con macOS —
  **verificado en vivo**: arranca al iniciar el launcher y termina
  limpio al cerrar) y `WindowsWakeLock` (`SetThreadExecutionState` de
  `kernel32` vía `ctypes`, sin dependencia nueva — **sin verificar en
  hardware/VM Windows real**, mismo patrón de verificación pendiente
  que el resto de adapters específicos de Windows). Se libera al
  cerrar el launcher, junto con el resto de la limpieza de salida.
- **Al cerrar el launcher, se para la reproducción actual** (Kodi o
  Spotify, lo que estuviera sonando) antes de cerrar la ventana — antes
  el audio se quedaba sonando aunque el launcher ya no estuviera.
  Reutiliza `KodiGateway.stop()`/`SpotifyGateway.pause()`, ya
  existentes para la exclusión mutua; ambas llamadas son best-effort.
- **Fluidez del VU-metro configurable** (Ajustes → "Fluidez del
  VU-metro": Rápido/Normal/Fluido). Tres presets que escalan la misma
  ballística de ataque/liberación (`VU_SMOOTHING_PRESETS` en
  `ambar/domain/audio.py`): "Rápido" reacciona casi al instante (más
  nervioso, sigue de cerca cada transitorio), "Fluido" es más lento y
  amortiguado (movimiento más suave/cinematográfico). Nuevo
  `LevelMeter.set_ballistics()` y `AudioLevelService.set_smoothing()`
  para reconfigurar en caliente sin reiniciar el launcher, persistido
  como `VU_METER_SMOOTHING` en `config.json`. El watchdog de caída del
  frontend usa la misma tabla de presets para no desentonar con la
  ballística real del backend.
- **Tiempo de reproducción visible**: junto a la barra de progreso
  ahora se ve el tiempo transcurrido, el total de la pista y el que
  queda por sonar (antes solo se veía un "%"). Nuevos campos
  `elapsed_seconds`/`total_seconds` en `PlaybackState`, rellenados por
  Kodi (`Player.GetProperties` con `time`/`totaltime`) y Spotify
  (`progress_ms`/`duration_ms`).
- **Seleccionar una canción concreta de la lista de reproducción**
  actual (antes solo se podía ver, no interactuar): nuevo
  `KodiGateway.goto_position()` (`Player.GoTo` con una posición
  numérica de la playlist, verificado en vivo) y reutilización de
  `SpotifyGateway.play_track()` para Spotify. Enrutado por
  `PlaybackControlService.play_playlist_item()` vía
  `POST /api/now-playing/playlist/play`.
- **Iconos descriptivos en los botones de volumen** (🔉 −5, 🔇/🔊
  Silenciar/Reactivar según el estado actual, 🔊 +5).
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
- **Barra de progreso seekable**: click en cualquier punto de la barra
  de reproducción para adelantar/atrasar. Nuevo
  `KodiGateway.seek(percentage)` (`Player.Seek` con
  `value: {percentage}`) y `SpotifyGateway.seek(percentage)`
  (convierte a `position_ms` según la duración de la pista actual y
  llama a `seek_track`), enrutados por `PlaybackControlService.seek()`
  vía `POST /api/seek`. Actualización optimista en el frontend (la
  barra se mueve al click, sin esperar al próximo evento de estado).
- **Marquee para título/artista/álbum largos**: cuando el texto no
  cabe en `.track-title`/`.track-meta`, se desplaza lateralmente hasta
  leerse entero (pausa inicial y final antes de reiniciar), en vez de
  cortarse con `text-overflow:ellipsis`. Solo se activa si el texto
  realmente desborda (medido con `scrollWidth` contra el ancho del
  contenedor); textos cortos no animan.
- **Reproducir álbum o artista completo** desde la biblioteca de Kodi:
  botón "Reproducir todo de [artista]" en la vista de álbumes y
  "Reproducir álbum completo" en la vista de canciones. Kodi ya
  soporta `artistid`/`albumid` directamente en `Playlist.Add`
  (expande la lista de canciones correspondiente), así que solo hizo
  falta enrutar `artistid` en `LibraryService.kodi_play()` (`albumid`
  ya se pasaba) y añadir el botón en el frontend. Verificado en vivo
  contra Kodi real: reproducir por `artistid` expande y arranca la
  playlist correctamente.
- **Lista de reproducción actual visible desde el home**: botón ☰
  junto a la fuente activa que abre la playlist completa (no solo la
  pista actual), con la canción en curso resaltada. Nuevo
  `NowPlayingService.get_playlist()` (delega en `KodiGateway.get_playlist()`,
  vía `Playlist.GetItems` + `Player.GetProperties(position)`, o
  `SpotifyGateway.get_playlist()`, vía `sp.queue()`, según la fuente
  activa), expuesto en `GET /api/now-playing/playlist`. El estado
  visible/oculta persiste entre sesiones (`SHOW_PLAYLIST` en
  `config.json`/`/api/config`, igual que `VU_METER_STYLE`). Verificado
  en vivo contra Kodi real (playlist con pista en curso resaltada
  correctamente).
- **Skins personalizadas**: nuevo `SkinService.list_skins()` que
  detecta carpetas con `style.css` dentro de `/skins` (junto al
  ejecutable, no versionada — ver `.gitignore`), expuesto vía
  `GET /api/skins` y servido en `/skins/<archivo>`. Seleccionable
  desde Ajustes → "Skin personalizada", persistida como `SKIN` en
  `config.json`/`/api/config` y aplicada al momento (inyecta el
  `<link>` tras los estilos por defecto, sin recargar la página).
  Documentado en `docs/index.html` cómo crear una, incluidas las
  variables CSS de color (`--bg`, `--panel`, `--amber`...) que expone
  el launcher para facilitar el retema.
- **Guía inicial de configuración para Spotify/Kodi**: si no existe
  `config.json` previo (`JsonConfigRepository.exists()`,
  `ConfigService(is_first_run=...)`), el launcher abre solo el modal
  de Ajustes con un banner explicando los dos pasos iniciales (host de
  Kodi, credenciales de Spotify). Se puede volver a mostrar en
  cualquier momento con el botón "Mostrar guía inicial". La URL de
  autorización de Spotify ya no lleva un placeholder genérico
  (`IP_DE_ESTE_PC`) — se rellena con la IP real del equipo en la red
  local, obtenida vía `SystemService.get_lan_ip()` y
  `GET /api/system/network-info`.
- **Navegación de biblioteca consistente Kodi/Spotify**: las playlists
  de Spotify ahora abren primero su lista de canciones (con
  "Reproducir lista completa" arriba y cada pista reproducible por
  separado), igual que los álbumes de Kodi, en vez de arrancar la
  playlist entera al primer toque. Nuevo
  `SpotifyGateway.get_playlist_tracks()` (`sp.playlist_items()`) y
  `play_track()` (`sp.start_playback(uris=[...])`), expuestos vía
  `GET /api/library/spotify/playlist-tracks` y
  `POST /api/library/spotify/play-track` (con la misma exclusión mutua
  con Kodi que `spotify_play`).
- **Control de volumen del sistema**: panel deslizante en el home
  (botón 🔊 junto a la fuente activa) con slider, botones +5/−5 y
  silenciar, sondeado cada 2s mientras está visible para reflejar
  cambios de volumen hechos desde otro origen (teclado, mando, o el
  propio SO), no solo los del launcher. Nuevo puerto
  `VolumeController` con un adapter por plataforma
  (`ambar/adapters/audio/`): `MacVolumeController` (vía `osascript`,
  **verificado en vivo**: volumen real subido/bajado/silenciado y
  restaurado en macOS) y `WindowsVolumeController` (vía
  `pycaw`/`IAudioEndpointVolume`, **sin verificar en hardware/VM
  Windows real** — mismo patrón de verificación pendiente que el resto
  de adapters de audio). Expuesto vía `GET/POST /api/system/volume`.
  **Deliberadamente no incluye selector de dispositivo de salida** —
  ver `TODO.md` para la justificación (no hay API pública fiable para
  cambiar el dispositivo por defecto en ninguna de las dos
  plataformas).
- **Pantalla de arranque configurable** (Ajustes → Sistema → "Pantalla
  de arranque"), relevante porque el mini PC saca imagen a la vez a la
  pantalla táctil y a la TV. Usa el parámetro `screen` nativo de
  `pywebview.create_window()` en vez de coordenadas `x`/`y` a mano
  (que además tienen forma distinta por plataforma). `webview.screens`
  se enumera una única vez en el hilo principal al arrancar — antes de
  lanzar el hilo de fondo del servidor, respetando la misma
  restricción de hilo principal de pywebview en macOS que ya afecta al
  resto de la app — y se guarda como datos planos
  (`AppContainer.available_screens`) para que
  `GET /api/system/screens` lo sirva sin volver a tocar pywebview
  desde el hilo del servidor. El cambio se aplica al reiniciar el
  launcher (la ventana nativa solo se crea una vez al arrancar).
  Verificado en macOS con una pantalla; sin verificar con varios
  monitores conectados a la vez.
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
- **`config.json`/`.spotify-cache`/skins no persistían en el binario
  compilado.** Causa raíz: en un `.app`/`.exe` empaquetado con
  PyInstaller, `__file__` no apunta junto al ejecutable real, sino
  dentro del bundle interno (`Contents/Frameworks/` en macOS,
  confirmado en vivo compilando y viendo dónde acababa `config.json`)
  — una carpeta que `python build.py` borra y recrea entera en cada
  build (`--clean`), así que cualquier ajuste guardado se perdía en el
  siguiente build. Arreglado usando `sys.executable` (no `__file__`)
  para localizar el ejecutable real, manteniendo el requisito de que
  `config.json` viva **junto al ejecutable** en ambas plataformas: en
  Windows, `sys.executable` ya apunta directamente a esa carpeta; en
  macOS, como el ejecutable real vive dentro del bundle
  (`Ambar.app/Contents/MacOS/Ambar`, que se borra y recrea entero en
  cada build), se sube hasta encontrar la carpeta `.app` y se usa su
  carpeta *contenedora* — el mismo sitio donde el usuario ve el icono
  de `Ambar.app` en Finder, junto a él pero fuera del bundle, así que
  sobrevive a las recompilaciones (PyInstaller solo borra/recrea
  `Ambar.app` en sí, no sus hermanos). El modo desarrollo
  (`python kiosk_server.py`) no cambia: sigue guardando junto al
  código, como siempre. Verificado en vivo compilando dos veces
  seguidas en macOS y confirmando que un ajuste guardado sobrevive a
  la segunda compilación, apareciendo como fichero junto a
  `Ambar.app`, no dentro.
- **El estado "Reproduciendo"/"Pausa" (y la carátula) podían quedarse
  congelados** si se perdía algún evento `playback_update` del
  WebSocket (p. ej. por el mismo tipo de problema de conectividad ya
  visto con el listener de eventos de Kodi en la VM de Windows). El
  frontend dependía al 100% del WebSocket, sin ningún sondeo de
  respaldo. Ahora hay un sondeo cada 5s a `/api/now-playing`
  independiente del WebSocket (mismo principio que el watchdog de
  caída del VU-metro: no confiar solo en que el backend siga
  publicando eventos), lo que de paso también arregla el spinner de
  carátula (dependía de que `render()` se llamase para detectar un
  cambio de pista).
- **"Reproducir Carpeta entera" (y "Reproducir CD entero") no hacía
  nada.** Causa: se llamaba a `Playlist.Add` con
  `item: {file: <ruta-de-carpeta>}` — `file` es para un fichero
  individual, y Kodi devuelve `Invalid params` si se le pasa una
  carpeta ahí (verificado en vivo contra Kodi real). El campo correcto
  para reproducir el contenido completo de una carpeta es `directory`,
  no `file` (`Playlist.Add` con `directory` expande todas las pistas
  correctamente, también verificado en vivo). Ahora
  `LibraryService.kodi_play()` distingue `directory` de `file`, y el
  botón de "reproducir entero" en `renderDirectoryList` (usado tanto
  por Carpetas como por CD) envía `directory`. De paso se sustituye el
  `onclick` inline de ese botón (interpolaba la ruta sin escapar en un
  atributo HTML — frágil ante rutas con comillas u otros caracteres
  especiales) por `addEventListener`, igual que el resto de la app.
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
