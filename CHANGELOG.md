# Changelog

Todos los cambios notables de este proyecto se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Changed
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
