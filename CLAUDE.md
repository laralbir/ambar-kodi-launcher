# Ámbar — contexto del proyecto

Nombre del proyecto: **Ámbar**, por el acento ámbar tipo display
VFD/LED que define la estética del launcher.

Panel táctil para una estación multimedia HiFi (mini PC + amplificador
Pioneer SA-508), pensado para vivir en `/Users/carlos/Projects/hifi-codi-launcher`.

## Mantenimiento de la documentación

Cada vez que un cambio afecte a cómo se instala, se usa, se compila o
se publica el proyecto, hay que mantener actualizados en el mismo
commit:

- `README.md`
- `CHANGELOG.md`
- la guía de usuario en `docs/`

El trabajo pendiente (backlog) vive en `TODO.md`, no en este fichero.
Al completar algo de `TODO.md`, muévelo a `CHANGELOG.md` en vez de
simplemente borrarlo.

## Hardware

- **Mini PC**: Intel N100, 16GB RAM, 512GB SSD, Windows 11 preinstalado,
  triple salida de vídeo (HDMI + USB-C + otra), WiFi6/BT5.2.
- **Pantalla táctil**: 10.3" USB-C, formato panorámico bajo ("stretched
  bar", ~1920x720). Conectada al mini PC como segundo monitor.
- **TV**: LG 55" por HDMI — pantalla "tonta" de salida, sin lógica propia.
- **Cadena de audio**: mini PC (USB) → adaptador Cubilux USB a
  óptico/coaxial SPDIF → DAC LiNKFOR DAC104eu (óptico/coaxial/Bluetooth
  a RCA) → entrada del Pioneer SA-508.
- **Mando**: JZK G20S Pro Plus, air mouse con dongle 2.4G/BT5.0 y
  aprendizaje IR. Funciona como HID estándar (teclado/ratón), sin
  drivers especiales.
- **CD**: lector CD/DVD externo USB.

## Objetivo

Reproducir MP3/FLAC, Spotify y CD de audio, controlado todo desde la
pantalla táctil (launcher propio) y desde el mando. La TV solo muestra
lo que Kodi está reproduciendo; la pantalla táctil es el mando central.

## Decisiones de arquitectura tomadas

- **Sistema**: Windows 11 (el que ya trae el mini PC), para evitar la
  fricción de montar todo a mano en Linux (no existe una distro que
  cubra dual-screen + Spotify + CD + táctil "de fábrica").
- **Reproductor principal / TV**: Kodi en pantalla completa por HDMI.
  Cubre FLAC/MP3 (biblioteca nativa) y CD (fuente `cdda://` nativa,
  detecta el lector externo).
- **Spotify**: no hay integración oficial ni fiable dentro de Kodi (los
  plugins no oficiales llevan años rotos). El launcher se ejecuta en la
  misma máquina que reproduce (Spotify de escritorio en el propio mini
  PC, no el modelo "Connect desde el móvil" que se planteó al principio),
  así que "ahora suena" y el transporte (play/pause/siguiente/anterior/
  seek) usan **SMTC** (`Windows.Media.Control`, vía los paquetes
  modulares `winrt-Windows.*` — ver
  `ambar/adapters/media_session/windows_smtc.py`) en vez de la Web API de
  Spotify: es una API nativa de Windows sin autenticación ni límite de
  peticiones (la misma que usa el propio Windows para el mini-reproductor
  de la barra de tareas), con lo que se evita por completo el problema de
  rate-limit de la Web API (ver `CHANGELOG.md`, `rate_limited_until`).
  `SpotifyGateway` (Spotipy, Web API) sigue siendo necesaria para lo que
  SMTC no cubre — listar playlists/artistas seguidos/álbumes guardados,
  y **arrancar** una reproducción nueva elegida desde la biblioteca del
  launcher (`play_context`/`play_track`, sin equivalente en SMTC, que solo
  controla una sesión ya en marcha) — y como red de respaldo automática
  si no hay sesión SMTC local (Spotify de escritorio cerrado, o en
  macOS/desarrollo, donde SMTC no existe). No se intenta embeber el
  reproductor web de Spotify (Spotify bloquea el embebido con
  X-Frame-Options).
- **Mando remoto (JZK G20S Pro)**: sus teclas multimedia (play/pausa/
  siguiente/anterior) son globales de Windows y el sistema las enruta a
  la sesión SMTC que considere "actual" — Spotify ya se registra como
  una y las recibe bien, pero Kodi no se registra como sesión SMTC por
  sí mismo en Windows (sin soporte nativo ni addon para ello, confirmado
  buscando: forum.kodi.tv/showthread.php?tid=375121), así que esas
  teclas no le llegaban nunca reproduciendo desde Kodi. Arreglado
  publicando una sesión SMTC propia (`ambar/adapters/media_session/
  windows_smtc_publisher.py`, vía un `MediaPlayer` de WinRT usado solo
  como vehículo para obtener el objeto `SystemMediaTransportControls` —
  no reproduce audio real) que representa a Kodi y solo se activa
  mientras Kodi es la fuente que suena, cerrándose el resto del tiempo
  para no competir con la sesión nativa de Spotify. Verificado en vivo
  simulando las teclas de sistema (no solo con el mando real). Además,
  como es un mando combo teclado+ratón, el D-pad manda flechas y "OK"
  manda Enter — el propio `index.html` (final del script) implementa
  navegación completa de la interfaz con eso: navegación *espacial*
  (busca el elemento visible más cercano en la dirección pedida, no
  orden del DOM) sobre una lista de selectores CSS genérica (reutiliza
  las clases que ya usan `renderGrid`/`renderList`/etc., sin tocarlas ni
  mantener una lista de foco cacheada), con guardas para no interceptar
  las flechas dentro de campos de texto y para descartar el "click
  fantasma" que estos mandos disparan a la vez que Enter en la posición
  del cursor real (no sobre el elemento con foco del D-pad).
- **Ventana kiosko**: `frameless=True` en pywebview activa `easy_drag`
  por defecto en el backend EdgeChromium de Windows (arrastra la ventana
  del sistema al primer `mousedown` en cualquier punto de la página,
  confirmado que afectaba incluso al slider de volumen) — desactivado
  explícitamente (`easy_drag=False`) en `bootstrap.py`, no hace falta
  arrastre nunca en un kiosko fijo a la pantalla táctil. Además, Ámbar
  se bloquea a una sola instancia a la vez (`_acquire_single_instance_lock`
  en `bootstrap.py`, reserva un puerto TCP local fijo como mutex).
- **Exclusión mutua entre fuentes**: además de que `kodi_play()`/
  `spotify_play()` paren la otra fuente al arrancar reproducción desde
  la biblioteca del propio launcher, `NowPlayingService.
  enforce_single_source()` (sondeado cada 3s desde el poller de Spotify)
  detecta cuándo una fuente empieza a sonar por su cuenta (mando, el
  propio Kodi, Spotify Connect desde el móvil...) mientras la otra ya
  estaba sonando, y pausa la otra.
- **Launcher táctil**: página propia (`index.html`) servida por un
  único servidor local Flask (`kiosk_server.py`) que:
  - unifica el estado de "ahora suena" de Kodi (JSON-RPC) y de Spotify
    (Spotipy), evitando problemas de CORS en el navegador kiosko;
  - expone `/api/now-playing`, `/api/control`, `/api/art`, `/login`,
    `/callback`;
  - sirve `index.html` en `/`.
  - El navegador del kiosko debe apuntar a `http://127.0.0.1:5005`
    (no abrir `index.html` como archivo suelto, y no usar el nombre
    "localhost" -- ver bootstrap.py: el servidor solo escucha en IPv4,
    pero "localhost" en Windows resuelve primero a IPv6 y cada petición
    pagaba ~2s de más esperando el rechazo de esa ruta antes de caer a
    IPv4, notándose como controles de reproducción "colgados").
- **Vista de biblioteca**: dentro del propio launcher, navegación nativa
  de artistas/álbumes/canciones/carpetas/CD contra la API JSON-RPC de
  Kodi (`ambar/adapters/kodi/gateway.py`, expuesto vía
  `/api/library/kodi/*`) — sin iframe ni webinterface externo.
- Kodi solo necesita tener activado `Ajustes > Servicios > Control >
  Permitir control remoto vía HTTP`.

## Diseño visual (launcher)

Estética "receptor HiFi vintage": panel gunmetal (#17181a/#1f2124),
acento ámbar tipo display VFD/LED (#ffb020), tipografía Oswald
(títulos condensados) + JetBrains Mono (datos/tiempos) + Inter (UI).
Barra de progreso estilo VU-meter segmentado (`.vu-bar`/`.vu-fill`,
progreso de reproducción — no confundir con el VU-metro de nivel real
de audio, `.vu-meter-leds`/`.vu-meter-needle`, ver sección "VU-metro"
más abajo). Layout horizontal
pensado para el formato panorámico bajo de la pantalla táctil:
carátula a la izquierda, info + transporte en el centro, accesos a
Biblioteca/Spotify a la derecha.

El layout está calculado explícitamente para **1920x720 a pantalla
completa** (no solo "panorámico bajo" en genérico): carátula y
columna de accesos a 82vh de alto, tipografía y controles
dimensionados para esa resolución exacta.

## Estructura de archivos

- `index.html` — launcher (HTML/CSS/JS en un solo archivo).
- `kiosk_server.py` — **entrypoint fino**. Solo llama a
  `ambar.bootstrap.run(app_dir)`. Vive en la raíz porque
  `build.py`/PyInstaller lo referencian como script de entrada.
- `ambar/` — paquete con toda la lógica, en arquitectura hexagonal /
  DDD-lite / event-driven:
  - `domain/` — `PlaybackState` (value object), `PlaybackStateChanged`
    (evento de dominio). Sin dependencias de infraestructura.
  - `application/` — casos de uso: `NowPlayingService` (decide si
    manda Kodi o Spotify), `PlaybackControlService`, `LibraryService`,
    `SystemService`, `ConfigService`, `SkinService` (lista las skins
    personalizadas en `/skins`, ver más abajo), y `EventBus` (pub/sub
    interno: desacopla "detectar un cambio" de "emitirlo por
    WebSocket").
  - `ports/` — protocolos que implementan los adapters:
    `PlaybackSource`, `ConfigRepository`, `WindowController`.
  - `adapters/` — infraestructura real: `kodi/` (gateway JSON-RPC +
    listener de WebSocket), `spotify/` (gateway Spotipy + poller),
    `media_session/` (SMTC de Windows para ahora-suena/control de Spotify
    local, ver sección "Spotify" arriba — solo Windows, `SpotifyGateway`
    cae a la Web API si no está disponible), `persistence/` (config en
    JSON), `web/` (rutas Flask +
    `SocketIOBridge`, el único sitio que sabe que existe SocketIO),
    `desktop/` (ventana pywebview), `audio/` (captura de audio para
    el VU-metro: `windows_wasapi.py`, `macos_screencapturekit.py`,
    `null_source.py` como fallback — ver "VU-metro" abajo).
  - `bootstrap.py` — composition root: construye los adapters, los
    inyecta en los servicios, conecta el `EventBus` y arranca el
    servidor (+ ventana nativa si aplica).
  - **Nota de proporcionalidad:** para el tamaño de esta app, "DDD" es
    ligero a propósito — Kodi y Spotify son un único adapter "gateway"
    cada uno, no se fragmentan en agregados/repositorios artificiales.
  - Ninguna ruta HTTP, payload JSON ni comportamiento observable
    cambió al introducir esta estructura (ver `CHANGELOG.md`).
- `tests/` — `pytest` sobre `NowPlayingService` (con dobles de
  `PlaybackSource`, sin red real). `requirements-dev.txt` añade
  `pytest` sobre `requirements.txt` sin inflar el build de PyInstaller.
- `config.json` — credenciales/host de Kodi y Spotify persistidos en
  disco (no versionar, ver `.gitignore`). Vive **junto al ejecutable**,
  igual en Windows y macOS (`ambar/bootstrap.py:_get_data_dir`): en
  modo desarrollo, junto al código; en el binario compilado, usa
  `sys.executable` (no `__file__`, que en un app frozen de PyInstaller
  no apunta junto al `.exe`/`.app` real, sino dentro del bundle
  interno). En Windows eso ya es la carpeta del `.exe` directamente; en
  macOS, como el ejecutable real vive dentro del bundle
  (`Ambar.app/Contents/MacOS/Ambar`) y ese bundle se borra y recrea
  entero en cada `python build.py`, se sube hasta encontrar la carpeta
  `.app` y se usa su carpeta *contenedora* (junto al icono de
  `Ambar.app`, no dentro) — así sobrevive a las recompilaciones,
  verificado en vivo compilando dos veces seguidas.
- `.spotify-cache` — se genera solo tras autorizar Spotify (no
  versionar), en el mismo directorio que `config.json` (ver arriba).
- `build.py` / `Ambar.spec` — empaquetado con PyInstaller
  (`--windowed`, icono, `collect-all` de engineio/socketio,
  `hidden-import` de websocket/spotipy/simple_websocket). Genera
  `.exe` en Windows y `.app` en macOS; el binario siempre corresponde
  al SO en el que se ejecuta PyInstaller.

## Entorno de desarrollo

- El desarrollo diario ocurre en **macOS** (este repo), aunque el
  destino final del mini PC es Windows 11. `kiosk_server.py` es
  cross-platform (usa `sys.platform` para diferenciar shutdown/restart
  de Windows vs. Unix).
- Tras tocar `requirements.txt`, reinstalar en el venv del repo
  (`venv/bin/pip install -r requirements.txt`) — es fácil que el venv
  quede desincronizado si se edita el fichero sin reinstalar.
- **No usar `eventlet`.** Se probó y se quitó por completo (ver
  `CHANGELOG.md`, sección `[Unreleased] > Removed`): además de tener
  problemas de compatibilidad con Python 3.13 y con el empaquetado de
  PyInstaller (`dnspython`/`dns`), **causaba una pantalla en negro al
  abrir la ventana en macOS** — `webview.start()` en el hilo principal
  (bucle nativo de Cocoa vía PyObjC) acapara el GIL, y el hub de
  eventlet en el hilo de fondo dejaba de recibir tiempo de CPU, así
  que el servidor quedaba escuchando pero nunca respondía. Flask-
  SocketIO usa `async_mode="threading"` (con el paquete
  `simple-websocket` para WebSockets reales) y los hilos de fondo de
  Kodi/Spotify usan `threading.Thread` normal — un servidor con hilos
  nativos convive bien con `webview.start()`, uno basado en eventlet
  no.
- **pywebview exige correr en el hilo principal en macOS** (restricción
  de Cocoa/AppKit; en Windows no aplica, por eso no se detectó antes).
  Por eso `ambar/bootstrap.py` lanza el servidor Flask-SocketIO (y los
  hilos de Kodi/Spotify) en un hilo de fondo, y deja `webview.start()`
  en el hilo principal.
- El primer arranque del `.app` recién compilado por PyInstaller puede
  tardar unos segundos más en responder por HTTP (verificación de
  Gatekeeper del bundle recién firmado); en arranques posteriores es
  inmediato. No es un cuelgue — si tarda más de ~10s sí investigar.

## VU-metro (nivel real de audio)

- Configurable desde Ajustes (`VU_METER_STYLE`: `"leds"` o `"needle"`,
  persistido en `config.json` como el resto de la configuración).
  **No** es una animación decorativa: mide de verdad el audio de
  salida del sistema (loopback), con un adapter distinto por
  plataforma (`ambar/adapters/audio/`) tras el puerto
  `AudioLevelSource`.
- **Estéreo**: un medidor por canal (L/R), cada uno con su propio
  `LevelMeter` en `AudioLevelService` y su propia leyenda de dB junto
  al medidor (`-Inf dB` en silencio total, escala logarítmica —
  intencionado, no un bug). Zonas de saturación ámbar/rojo dibujadas
  en la propia escala (arco de color en la aguja, fondo tintado en las
  barras LED apagadas), no solo cuando el nivel las alcanza. Si el
  audio calla, el medidor cae de forma progresiva hasta -60dB en vez
  de congelarse — hay un watchdog de decaimiento también en el
  frontend (`index.html`, `VU_IDLE_MS`) como red de seguridad
  independiente de si el backend sigue publicando eventos.
- **macOS** (entorno de desarrollo): `ScreenCaptureKit` (macOS 13+),
  vía PyObjC, sin driver adicional. Pide permiso de "Grabación de
  pantalla" la primera vez (System Settings > Privacy & Security).
  Verificado en vivo end-to-end (audio real → WebSocket → cliente).
  **Detalle no obvio (extracción de PCM):** usa
  `CMBlockBufferCopyDataBytes`, NO
  `CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer` — esta
  última tiene metadatos de bridging rotos en
  `pyobjc-framework-CoreMedia` 12.2.1 para su parámetro de salida
  `AudioBufferList` (probado exhaustivamente: `bytearray`, `ctypes`
  en varias formas, `NSMutableData`, `objc.createStructType` — todos
  rechazados con `ValueError("depythonifying 'pointer'...")`). Si en
  el futuro se toca este adapter y algo similar vuelve a fallar, no
  perder tiempo ahí: usar el camino de `CMBlockBufferCopyDataBytes`
  (bien anotado por PyObjC, funciona directo).
  **Detalle no obvio (layout estéreo):** el buffer de audio de
  ScreenCaptureKit con `channelCount=2` es *planar*, no intercalado —
  todo el canal 0 seguido de todo el canal 1 en el mismo array plano
  (`samples[:n/2]` = izquierdo, `samples[n/2:]` = derecho), NO
  muestras L/R alternadas. Confirmado en vivo leyendo el
  `AudioStreamBasicDescription` (flag `kAudioFormatFlagIsNonInterleaved`
  activo) antes de asumir el formato.
  **Limitación conocida de macOS (no arreglable desde la app, ver
  `TODO.md`):** `build.py` firma el `.app` de forma *ad-hoc* (sin
  certificado de Apple Developer). Esto puede hacer que la app no
  aparezca sola en Ajustes del Sistema → Privacidad y Seguridad →
  Grabación de pantalla (añadirla a mano con "+"), y que el permiso se
  pierda en cada recompilación (firma distinta ⇒ macOS la trata como
  app nueva) — hay que volver a concederlo y **cerrar del todo y
  reabrir la app** tras hacerlo. Además, el permiso es independiente
  entre `python kiosk_server.py` (modo desarrollo, identidad = el
  interprete del venv, aparece en la lista como `kiosk_server` o
  `Python`/`python3.x`) y el `.app` compilado — concederlo a uno no
  vale para el otro, hay que darlo a ambos por separado. Documentado
  en `README.md` y `docs/index.html`.
  **Importante:** al cerrar la app (`SystemService.execute("exit")`)
  hay que llamar a `AudioLevelService.stop()` ANTES de cerrar la
  ventana — si el proceso empieza a finalizar mientras el stream de
  ScreenCaptureKit sigue disparando callbacks nativos de ObjC en un
  hilo de fondo, el intérprete revienta (visible como "Ambar-x se ha
  cerrado inesperadamente"). Ya arreglado, pero si se añaden más
  recursos nativos de fondo en el futuro, recordar pararlos también
  ahí antes de cerrar.
- **Windows** (producción, el mini PC real): captura WASAPI loopback
  vía el paquete `soundcard`, que entrega los canales ya separados
  (`(numframes, nchannels)`, sin necesidad de partir nada a mano).
  **Sin verificar en hardware/VM Windows real** — se desarrolló en
  macOS. Probar antes de confiar en ello.
- Si la captura falla por cualquier motivo (dependencia nativa
  ausente, permiso denegado, plataforma no soportada), cae a
  `NullAudioLevelSource`: el medidor queda inactivo, el resto de la
  app sigue funcionando con normalidad — nunca debe romper el arranque.
- `requirements.txt` usa marcadores de entorno PEP 508
  (`sys_platform == "win32"` / `"darwin"`) para que `soundcard` y los
  `pyobjc-framework-*` solo se instalen en su plataforma
  correspondiente.

## Pendiente / próximos pasos

Backlog completo en [`TODO.md`](TODO.md). Aquí solo lo más inmediato:

- Configurar credenciales de Spotify Developer Dashboard
  (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`) y autorizar una vez
  vía `/login` (ya hay UI de ajustes para introducirlas sin tocar
  variables de entorno).
- Posibles ajustes de diseño (tamaños, colores) a petición de Carlos.
- Validar en la pantalla táctil real el layout panorámico bajo.

## Versionado y releases

- Fuente única de la versión: fichero `VERSION` (semver, sin `v`).
  `build.py` lo lee para escribirla en el manifest (`CFBundleShortVersionString`/
  `CFBundleVersion` en macOS, recurso de versión en Windows) — el
  ejecutable en sí se llama siempre `Ambar` (sin versión en el nombre,
  a propósito: ver "VU-metro" para por qué el nombre estable importa
  también para los permisos de macOS).
- Historial de cambios en `CHANGELOG.md` (formato Keep a Changelog).
- `.github/workflows/release.yml`: al empujar un tag `vX.Y.Z`, compila
  con PyInstaller en `macos-latest` y `windows-latest` y publica una
  release en GitHub con los `.zip` de ambos SO adjuntos. Ver sección
  "Versionado y releases" del `README.md` para el flujo paso a paso.
- `Ambar.spec` es un artefacto generado por `build.py` (se borra y
  recrea en cada build) — no se versiona en git (`.gitignore` ya lo
  cubre con `*.spec`).
