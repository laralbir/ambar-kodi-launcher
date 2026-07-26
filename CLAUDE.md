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
  plugins no oficiales llevan años rotos). Se usa el modelo Spotify
  Connect: el usuario elige la reproducción desde el móvil, y el
  launcher la refleja/controla vía la Web API de Spotify (Spotipy),
  sin intentar embeber el reproductor web de Spotify (Spotify bloquea
  el embebido con X-Frame-Options).
- **Launcher táctil**: página propia (`index.html`) servida por un
  único servidor local Flask (`kiosk_server.py`) que:
  - unifica el estado de "ahora suena" de Kodi (JSON-RPC) y de Spotify
    (Spotipy), evitando problemas de CORS en el navegador kiosko;
  - expone `/api/now-playing`, `/api/control`, `/api/art`, `/login`,
    `/callback`;
  - sirve `index.html` en `/`.
  - El navegador del kiosko debe apuntar a `http://localhost:5005`
    (no abrir `index.html` como archivo suelto).
- **Vista de biblioteca**: dentro del propio launcher, botón "Biblioteca"
  abre en iframe el webinterface de Kodi/Chorus2 (`http://localhost:8080`)
  para navegar FLAC/MP3/CD, con botón de volver.
- Kodi debe tener activado `Ajustes > Servicios > Control > Permitir
  control remoto vía HTTP` y el addon **Chorus2** instalado.

## Diseño visual (launcher)

Estética "receptor HiFi vintage": panel gunmetal (#17181a/#1f2124),
acento ámbar tipo display VFD/LED (#ffb020), tipografía Oswald
(títulos condensados) + JetBrains Mono (datos/tiempos) + Inter (UI).
Barra de progreso estilo VU-meter segmentado. Layout horizontal
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
    `SystemService`, `ConfigService`, y `EventBus` (pub/sub interno:
    desacopla "detectar un cambio" de "emitirlo por WebSocket").
  - `ports/` — protocolos que implementan los adapters:
    `PlaybackSource`, `ConfigRepository`, `WindowController`.
  - `adapters/` — infraestructura real: `kodi/` (gateway JSON-RPC +
    listener de WebSocket), `spotify/` (gateway Spotipy + poller),
    `persistence/` (config en JSON), `web/` (rutas Flask +
    `SocketIOBridge`, el único sitio que sabe que existe SocketIO),
    `desktop/` (ventana pywebview).
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
  disco (no versionar, ver `.gitignore`).
- `.spotify-cache` — se genera solo tras autorizar Spotify (no versionar).
- `build.py` / `kiosk_server.spec` — empaquetado con PyInstaller
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

## Pendiente / próximos pasos

- Configurar credenciales de Spotify Developer Dashboard
  (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`) y autorizar una vez
  vía `/login` (ya hay UI de ajustes para introducirlas sin tocar
  variables de entorno).
- Posibles ajustes de diseño (tamaños, colores) a petición de Carlos.
- Validar en la pantalla táctil real el layout panorámico bajo.

## Versionado y releases

- Fuente única de la versión: fichero `VERSION` (semver, sin `v`).
  `build.py` lo lee para nombrar el ejecutable (`Ambar-{version}`).
- Historial de cambios en `CHANGELOG.md` (formato Keep a Changelog).
- `.github/workflows/release.yml`: al empujar un tag `vX.Y.Z`, compila
  con PyInstaller en `macos-latest` y `windows-latest` y publica una
  release en GitHub con los `.zip` de ambos SO adjuntos. Ver sección
  "Versionado y releases" del `README.md` para el flujo paso a paso.
- `kiosk_server.spec` es un artefacto generado por `build.py` (se
  borra y recrea en cada build) — no se versiona en git (`.gitignore`
  ya lo cubre con `*.spec`).
