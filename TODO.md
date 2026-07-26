# TODO — Ámbar

Lista de trabajo pendiente. Cuando se complete un punto, muévelo al
`CHANGELOG.md` (sección `[Unreleased]`) en vez de simplemente borrarlo
de aquí.

## Bugs conocidos (biblioteca)

- Las carátulas no aparecen en el listado de artistas. **Investigado:
  no es un bug de la app** — Kodi devuelve `thumbnail: ""` para todos
  los artistas de esta biblioteca (no tiene imágenes de artista
  scrapeadas/asignadas; los álbumes sí tienen carátula). El código ya
  gestiona bien el caso sin imagen (muestra el icono de nota musical
  en vez de una imagen rota). Posible mejora futura: usar la carátula
  del primer álbum como sustituto cuando no hay imagen de artista —
  no implementado, decir si se quiere.
- **Detección de CD de audio poco fiable en macOS.** Confirmado con
  `diskutil` que un CD insertado real (Redbook, `CD_partition_scheme`
  con particiones `CD_DA`) sigue dando `system.hasmediadvdaudio: false`
  en Kodi, y `cdda://local/` da "Invalid params" pase lo que pase — no
  hay ajuste de Kodi ni addon que lo explique, parece un límite de los
  builds de Kodi para macOS (su soporte de lectura nativa de CD de
  audio ahí es históricamente más débil que en Windows/Linux). **No
  se ha parcheado con nada específico de macOS** (p. ej. mirar
  `/Volumes/` vía `diskutil`) porque rompería la paridad de
  comportamiento con Windows. Mientras tanto: en macOS la pestaña "CD"
  nunca se deshabilita (no hay forma fiable de saberlo) y se muestra
  un aviso al entrar; en Windows/Linux sí se habilita/deshabilita
  según `system.hasmediadvdaudio` real. **Pendiente de confirmar si
  Kodi para Windows detecta correctamente el CD en el mini PC real.**

## Pendiente

- **Evitar que la pantalla se apague, salte el salvapantallas o el
  equipo entre en reposo** mientras Ámbar está en ejecución (relevante
  para un kiosko que se supone siempre visible/activo). Necesita un
  mecanismo por plataforma: Windows vía `SetThreadExecutionState`
  (`ES_DISPLAY_REQUIRED | ES_CONTINUOUS`, API de `kernel32` vía
  `ctypes`, sin dependencia nueva); macOS vía `caffeinate` (proceso
  auxiliar) o la API de IOKit `IOPMAssertionCreateWithName`. No
  implementado todavía.
- **VU-meter en el mini PC real**: verificado en macOS y en una VM
  Windows 11 ARM64 (ver `CHANGELOG.md`) — pendiente solo confirmarlo
  también en el hardware Windows real (Intel N100).
- **Firma de código estable para el `.app` de macOS**: ahora mismo
  `build.py` firma en modo *ad-hoc* (`codesign_identity=None`), lo que
  hace que el permiso de "Grabación de pantalla" del VU-metro se
  pueda perder en cada recompilación y que la app no siempre aparezca
  sola en Ajustes del Sistema (hay que añadirla a mano). Firmar con un
  certificado de código local estable (o uno de Apple Developer)
  fijaría la identidad entre builds y evitaría tener que re-conceder
  el permiso cada vez. Documentado como limitación conocida en
  `README.md` y `docs/index.html` mientras tanto. Ya se estabilizaron
  `--osx-bundle-identifier` y el nombre del binario (`Ambar`, sin
  versión) para reducir cuánto cambia entre builds — la firma ad-hoc
  en sí sigue siendo la causa raíz que falta arreglar del todo.
- **Selector de salida de audio del sistema** (HDMI TV, analógico,
  óptico...). **Deliberadamente no implementado todavía**: aunque
  `soundcard` (ya usado por el VU-metro) permite *listar* los
  dispositivos de salida en ambas plataformas
  (`soundcard.all_speakers()`), *cambiar* el dispositivo de salida por
  defecto del sistema no tiene una API pública fiable — en Windows
  requiere la interfaz COM no documentada `IPolicyConfig` (sin
  soporte oficial de Microsoft, con riesgo real de romper en
  distintas builds de Windows), y en macOS requiere CoreAudio de bajo
  nivel (`AudioObjectSetPropertyData` sobre
  `kAudioHardwarePropertyDefaultOutputDevice`). Implementarlo a
  ciegas sin poder verificarlo en el mini PC real es más probable que
  rompa el cambio de salida de audio que lo arregle. Pendiente de
  abordar cuando se pueda probar en hardware real.

## Hecho recientemente (ver `CHANGELOG.md` para el detalle completo)

- Refactor a arquitectura hexagonal/DDD-lite/event-driven (`ambar/`).
- Fix de la pantalla en negro en macOS (eliminación de `eventlet`).
- Gestión de versiones y releases automáticas por GitHub Actions.
- VU-meter estéreo con nivel real de audio (macOS vía ScreenCaptureKit
  y Windows vía WASAPI/`soundcard` verificados en vivo, este último en
  una VM Windows 11 ARM64 con Python x64 — audio real reproducido en
  la propia VM, medidor respondiendo correctamente).
- Fix de las carátulas de Kodi que no cargaban (doble-decodificación
  de la URL `image://` al hacer de proxy hacia Kodi).
- Fix del título "undefined" en el listado de álbumes (el frontend
  pedía el campo `title`, Kodi solo devuelve `label`).
- Fix de la pestaña CD/carpetas, que no funcionaba nunca: Kodi
  devuelve "Invalid params" para `Files.GetDirectory` con
  `directory="sources://music/"` en esta build (bug/limitación de
  Kodi, no nuestro) — se usa `Files.GetSources` para el nivel raíz.
- Exclusión mutua Kodi ↔ Spotify: al reproducir algo desde la
  biblioteca de una fuente se para automáticamente la otra si estaba
  sonando.
- Las pestañas/accesos de Kodi y Spotify se deshabilitan solos si esa
  fuente no responde (Kodi) o no está autorizada todavía (Spotify),
  comprobado al cargar y cada 15s.
- Spinner de carga en la carátula de "ahora suena" mientras se
  descarga la imagen (los listados de biblioteca ya tenían uno).
- Barra de progreso de reproducción seekable: click en cualquier punto
  de la barra para adelantar/atrasar (`Player.Seek` en Kodi,
  `seek_track` en Spotify).
- Marquee para título/artista/álbum cuando el texto no cabe: se
  desplaza lateralmente hasta leerse entero, con pausa inicial y al
  final antes de reiniciar, como en los displays de las autorradios.
- Reproducir un álbum o artista completo desde la biblioteca de Kodi
  ("Reproducir todo de [artista]" al ver sus álbumes, "Reproducir
  álbum completo" al ver sus canciones), no solo una canción suelta.
  Kodi ya soporta `artistid`/`albumid` en `Playlist.Add` — expande
  solo la lista de canciones correspondiente.
- Lista de reproducción actual visible desde el home (botón ☰ junto a
  la fuente activa): muestra la playlist completa de Kodi
  (`Playlist.GetItems`) o la cola de Spotify (`sp.queue()`) según la
  fuente activa, con la pista en curso resaltada. Se puede
  ocultar/mostrar, y ese estado persiste entre sesiones vía
  `SHOW_PLAYLIST` en `config.json`/`/api/config`.
- Skins personalizadas cargables desde `/skins/<nombre>/style.css`
  (carpeta junto al ejecutable, no versionada), seleccionable desde
  Ajustes y persistida vía `SKIN` en `config.json`. Documentado cómo
  crear una en la guía de usuario (`docs/index.html`), incluidas las
  variables CSS de color que expone el launcher.
- Conexión con Spotify más amigable: guía inicial integrada en el
  propio modal de Ajustes (se abre sola si no hay `config.json`
  previo, y se puede volver a mostrar en cualquier momento con
  "Mostrar guía inicial"), con la URL de autorización ya rellena con
  la IP real del equipo (`GET /api/system/network-info`) en vez de un
  placeholder genérico que había que editar a mano. El flujo de
  `/login`→`/callback` en sí ya no requería copiar/pegar URLs (Flask
  captura el `code` del redirect automáticamente).
- Navegación de biblioteca consistente entre Kodi y Spotify: las
  playlists de Spotify ahora tienen el mismo patrón de dos niveles que
  álbumes de Kodi (lista → canciones, con "reproducir lista completa"
  arriba y cada canción individual reproducible por separado), en vez
  de reproducir la playlist entera al primer toque.
- Control de volumen real del equipo (subir/bajar/silenciar, % visible)
  desde un panel deslizante en el home, sondeado cada 2s mientras está
  abierto para reflejar cambios hechos desde otro origen (teclado,
  mando, Ajustes del propio SO), no solo los del launcher. macOS vía
  `osascript` (verificado en vivo: volumen real subido/bajado/
  silenciado y restaurado); Windows vía `pycaw`/`IAudioEndpointVolume`
  (sin verificar en hardware/VM Windows real, mismo patrón que el resto
  de adapters de audio). El selector de dispositivo de salida queda
  fuera de este cambio (ver más arriba, en "Pendiente").
- Pantalla de arranque configurable desde Ajustes (relevante porque el
  mini PC saca a la vez a la pantalla táctil y a la TV): usa el
  parámetro `screen` nativo de `pywebview.create_window()` (no hace
  falta tocar coordenadas `x`/`y` a mano, que además tienen forma
  distinta por plataforma — `WorkingArea` en Windows,
  `NSScreen.frame()` en macOS). `webview.screens` se enumera una única
  vez en el hilo principal al arrancar (antes de lanzar ningún hilo de
  fondo, por la misma restricción de hilo principal de pywebview en
  macOS ya documentada para el resto de la app) y se guarda como datos
  planos en el `AppContainer` para que la ruta `GET /api/system/screens`
  pueda servirlo desde el hilo del servidor sin volver a tocar
  pywebview. El cambio se aplica al reiniciar el launcher, no en
  caliente (la ventana nativa solo se crea una vez al arrancar).
  Verificado en macOS con 1 pantalla (comportamiento sin romper el caso
  de un único monitor); sin verificar con más de un monitor conectado a
  la vez, al no haber hardware multi-monitor disponible en esta sesión.
