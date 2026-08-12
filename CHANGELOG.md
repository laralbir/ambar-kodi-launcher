# Changelog

Todos los cambios notables de este proyecto se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [0.5.0] - 2026-08-12

### Added
- **El mando (o cualquier teclado) ya puede pausar/cambiar de canción
  reproduciendo desde Kodi, no solo desde Spotify**. Causa real: en
  Windows, las teclas multimedia se enrutan a la sesión SMTC que el
  sistema considere "actual" — Spotify se registra como una sola (y
  Kodi no se registra como ninguna, confirmado que no tiene soporte
  nativo ni addon para ello, ver forum.kodi.tv/showthread.php?tid=375121),
  así que esas teclas siempre iban a Spotify sin importar qué sonara de
  verdad. Ahora Ámbar publica su propia sesión SMTC (`ambar/adapters/
  media_session/windows_smtc_publisher.py`) que representa a Kodi y solo
  se activa mientras Kodi es la fuente que suena (se cierra el resto del
  tiempo, para no competir con la sesión nativa de Spotify cuando es ella
  la que realmente está sonando). Verificado en vivo simulando las
  teclas de sistema Play/Pausa y Siguiente: Kodi reaccionó a las dos.
- **Solo puede sonar una fuente a la vez, sin importar desde dónde se
  inicie la reproducción** (mando, el propio Kodi, Spotify Connect desde
  el móvil...). Antes la exclusión mutua solo cubría el caso de arrancar
  reproducción *desde la biblioteca del propio launcher*
  (`kodi_play`/`spotify_play`); ahora `NowPlayingService.
  enforce_single_source()` detecta cuándo una fuente empieza a sonar
  mientras la otra ya estaba sonando y pausa la otra — sondeado cada 3s
  (`adapters/spotify/poller.py`).
- **Ámbar ya no permite arrancar una segunda instancia a la vez**: reserva
  un puerto TCP local fijo como mutex al arrancar (`_acquire_single_instance_lock`
  en `bootstrap.py`); si ya hay una instancia corriendo, la nueva se cierra
  sola con un aviso en el log. Verificado en vivo lanzando una segunda
  instancia con la primera ya corriendo.

### Fixed
- **Quitado el texto "SIN REPRODUCCIÓN" bajo el disco de la carátula
  vacía** en el home — ahora solo se muestra el icono de vinilo.
- **La ventana se podía arrastrar sin querer** (incluida la barra de
  volumen, y también en pantalla completa). Causa: pywebview activa
  `easy_drag` por defecto en ventanas sin bordes (`frameless=True`) en el
  backend EdgeChromium de Windows — engancha un listener de `mousedown`
  en toda la página que arrastra la ventana del sistema al primer
  movimiento, sea cual sea el elemento pulsado. Es un kiosko fijo en la
  pantalla táctil, no hace falta arrastre nunca — desactivado del todo
  (`easy_drag=False`).
- **La navegación por Kodi se notaba lenta**, causado sin querer por el
  propio arreglo de "solo una fuente a la vez" de arriba: la primera
  versión también reaccionaba al vuelo en cada evento `Player.OnPlay` de
  Kodi lanzando una consulta a Spotify (vía SMTC) justo cuando Kodi está
  más ocupado arrancando una pista. Quitada esa reacción inmediata (el
  sondeo periódico de 3s ya cubre el caso igual) y añadido un candado
  para que varias comprobaciones solapadas no se acumulen si una tarda
  de más.

## [0.4.0] - 2026-08-09

### Added
- **"Ahora suena" y el transporte de Spotify (play/pause/siguiente/
  anterior/seek) ya no dependen de su Web API — usan SMTC** (`Windows.
  Media.Control`, la misma API nativa que usa el propio Windows para el
  mini-reproductor de la barra de tareas), cuando el Spotify de escritorio
  está sonando en esta misma máquina. Sin autenticación, sin red, sin
  límite de peticiones — resuelve de raíz el problema de rate-limit
  descrito más abajo, en vez de solo mitigarlo. Nuevo adapter
  `ambar/adapters/media_session/windows_smtc.py` (paquetes modulares
  `winrt-Windows.*`, ver requirements.txt — NO el paquete "winsdk", que
  no publica rueda para Python 3.13 a fecha de este commit).
  `SpotifyGateway` lo usa con preferencia sobre la Web API y cae a esta
  automáticamente si no hay sesión SMTC local (reproduciendo desde el
  móvil por Connect, Spotify de escritorio cerrado, o en macOS/desarrollo,
  donde SMTC no existe). La Web API sigue siendo necesaria para lo que
  SMTC no cubre: listas/artistas seguidos/álbumes guardados, y arrancar
  una reproducción nueva desde la biblioteca del launcher. Verificado en
  vivo de punta a punta contra el Spotify de escritorio real: título,
  artista, álbum, carátula, progreso y control play/pause funcionando sin
  ninguna llamada a la Web API.
- **Aviso discreto cuando Spotify está bajo el límite de peticiones**: un
  429 de Spotify trae una cabecera `Retry-After` (segundos hasta que se
  puede reintentar) — ahora se guarda esa fecha (`SpotifyGateway.
  rate_limited_until`) y se expone en `/api/library/spotify/status`. El
  frontend muestra una franja pequeña en la parte inferior ("Spotify:
  límite de peticiones alcanzado. Se espera que se recupere sobre las
  HH:MM") solo una vez por cada límite nuevo, se cierra sola a los 10s (o
  antes con un click), y vuelve a aparecer si se produce un límite nuevo
  más adelante (fecha de recuperación distinta a la ya mostrada).
- **`scripts/setup_kiosk_windows.ps1`**: nuevo paso "Desactivar reproducción
  automática de CD de audio" (`PlayCDAudioOnArrival=MSTakeNoAction`) — sin
  esto, Windows puede abrir su propio reproductor multimedia a la vez que
  Kodi al insertar un CD, compitiendo por el lector y el audio. No afecta
  a como Kodi/Ámbar detectan el CD (no dependen del autoplay de Windows).
- **Reloj y VU-metro a pantalla completa muestran la canción actual**
  (título/artista) debajo, si hay algo sonando -- sin fuente activa, no se
  muestra nada. El reloj ahora también incluye segundos (`HH:MM:SS`),
  actualizándose cada segundo tanto en el home como a pantalla completa.
- **Carátulas de álbum y fotos de artista por búsqueda externa cuando Kodi
  no tiene una propia** (`kodi_albums`/`kodi_artists`), igual que ya se
  hacía para el CD: álbumes se buscan por texto (artista+título) en
  MusicBrainz + Cover Art Archive; artistas se buscan por nombre en
  Spotify (ya autorizado) y, si no está configurado o no lo encuentra,
  en Deezer (API pública, sin autenticación) como segundo respaldo.
  Álbumes limitado a 15 búsquedas externas por carga de pantalla para no
  bloquear la UI ni saturar esas APIs con bibliotecas grandes — el resto
  se va rellenando solo en visitas siguientes según se cachea. Artistas
  ya no tiene ese límite ni bloquea el listado (ver "Fixed" más abajo).
  **Bug real encontrado y arreglado en el camino**: la búsqueda de
  artista de Spotify con `limit=1` puede devolver un resultado top
  distinto (y equivocado) que con `limit=5` para la misma consulta —
  confirmado en vivo buscando "Erasure" y recibiendo "Depeche Mode" como
  único resultado. Ahora se piden 5 candidatos y se prefiere la
  coincidencia de nombre exacta entre ellos.
- **Vista de artista al tocar su nombre en "ahora suena"**: álbumes y
  canciones de ese artista, mezclando Kodi y Spotify. Si el mismo álbum
  está en las dos fuentes se muestra una sola vez (etiquetas "Kodi"/
  "Spotify"), con un selector para elegir desde dónde reproducirlo en vez
  de duplicarlo. Las canciones son solo de Kodi: `GET /artists/{id}/
  top-tracks` de Spotify también da 403 Forbidden para esta app (misma
  restricción de "Extended Quota Mode" que "Me gusta", ver más abajo).
  **Bug real encontrado y arreglado en el camino**: `get_artist_albums`
  (usado también por la pestaña "Artistas (Spotify)" ya existente)
  llevaba tiempo silenciosamente roto — el parámetro `limit` que envía
  `sp.artist_albums()` de spotipy hace que Spotify responda 400 "Invalid
  limit" **para cualquier valor**, incluso 5 o 20. Se llama ahora al
  helper HTTP interno de spotipy sin ese parámetro (Spotify pagina a 5
  por defecto) y se sigue la paginación a mano con `sp.next()`.

### Fixed
- **La navegación/reproducción de Kodi se notaba más lenta mientras
  Spotify estaba bajo el límite de peticiones**: `kodi_play()` llama a
  `spotify.pause()` antes de cada reproducción desde Kodi (para no dejar
  sonando algo de Spotify a la vez) — esa llamada seguía golpeando la API
  de Spotify (~0.5s de round-trip) aunque ya se supiera que iba a fallar.
  Ahora `SpotifyGateway._client()` (punto único por el que pasan todas
  las llamadas del gateway) corta en seco sin tocar la red si
  `rate_limited_until` sigue vigente. Ese corte no servía de nada si el
  límite nunca llegaba a registrarse: solo `get_state()` llamaba a
  `_record_rate_limit`, y mientras Kodi es la fuente activa
  `NowPlayingService` ni siquiera llega a invocar `spotify.get_state()`
  (Kodi tiene prioridad) — así que un 429 real de `pause()`/`control()`
  (las dos llamadas que sí se disparan desde Kodi: antes de cada
  reproducción, y desde los botones de transporte) quedaba sin detectar
  y se repetía en cada click. Ahora las tres registran el límite.
- **Spotify podía dejar "ahora suena" colgado indefinidamente ("nada
  sonando" para siempre) y hacer que "Salir" dejara de responder**.
  Causa real, confirmada en vivo haciendo la petición HTTP a mano:
  `GET /me/player` devolvía **429 "QUOTA_EXCEEDED"** (límite de
  peticiones de *esta app concreta* — no una caída general de Spotify)
  con cabecera `Retry-After: 53356` (~14.8 horas). Spotipy, con sus
  reintentos automáticos por defecto, usa urllib3 por debajo, que ante
  un 429 con `Retry-After` **duerme literalmente ese tiempo antes de
  reintentar** — así que la petición se quedaba dormida casi 15 horas
  por dentro, sin lanzar ninguna excepción y sin que ningún timeout de
  `requests` pudiera evitarlo (el timeout solo limita cada intento
  individual, no la espera entre reintentos). Con el sondeo de "ahora
  suena" cada 2s, cada petición colgada se quedaba abierta indefinidamente
  y se iban acumulando, hasta dejar al servidor sin hilos libres para
  atender nada más (incluida la ruta de "Salir", sin relación directa
  con Spotify). Arreglado desactivando los reintentos automáticos de
  spotipy (`retries=0`, `status_retries=0`) y añadiendo un timeout
  explícito de 10s tanto al cliente normal como a `SpotifyOAuth` (que no
  traía ninguno por defecto) — ahora un 429/error de red falla al
  momento en vez de colgarse, y el próximo sondeo (2s después) reintenta
  solo. El límite de peticiones en sí no lo soluciona esto (hay que
  esperar a que Spotify lo levante), pero dejar de martillear el
  endpoint de reproducción durante la ventana bloqueada ayuda a que se
  levante antes.
- **`/callback` de Spotify daba "Internal Server Error" en vez del mensaje
  de error normal** al recibir un código ya usado/caducado (los códigos de
  autorización de Spotify son de un solo uso y expiran a los pocos
  minutos) o si las credenciales cambiaban entre `/login` y `/callback`.
  `exchange_code` no capturaba la excepción de `get_access_token` — a
  diferencia de `_client()`, que ya tenía el mismo problema resuelto desde
  antes. Confirmado en vivo repitiendo la petición con un código inválido.
- **VU-metro de aguja realista: la etiqueta de dB se solapaba con la aguja**.
  `.vu-needle-footer` (etiqueta de canal + dB debajo del SVG) tenía un
  `margin-top` negativo pensado para acercarla al dial, pero la subía
  justo encima del pivote de la aguja, quedando visualmente encima/mezclada
  con ella. Cambiado a un margen positivo normal — ya no se tocan.
  Aprovechando el arreglo, la esfera analógica se hizo más realista:
  marcas de escala intermedias (no solo las 5 etiquetadas), cuatro
  tornillos de montaje en las esquinas del bisel, un brillo metálico a lo
  largo de la aguja, y un tamaño algo mayor.
- **Listado de "Álbumes" (Kodi) tardaba mucho en aparecer, mismo motivo que
  el de artistas** (ver siguiente entrada): `get_albums()` consultaba
  MusicBrainz por cada álbum sin carátula propia de forma síncrona antes
  de devolver la respuesta. Ahora el listado se devuelve al instante y el
  frontend pide la carátula de cada álbum sin ella aparte
  (`/api/library/kodi/album-art`, una petición por álbum en paralelo, con
  spinner), igual que ya se hizo para artistas.
- **Listado de "Artistas (Kodi)" tardaba mucho en aparecer**: `kodi_artists()`
  buscaba la foto de cada artista sin carátula propia (Spotify/Deezer, una
  consulta HTTP por artista) de forma síncrona antes de devolver la
  respuesta — con varios artistas sin foto, el listado entero esperaba a
  que todas esas búsquedas terminasen. Ahora el listado se devuelve al
  instante con lo que ya tiene Kodi, y el frontend pide la foto de cada
  artista sin ella aparte (`/api/library/kodi/artist-image`, una petición
  por artista, todas en paralelo — el servidor Flask-SocketIO ya corre
  con `threaded=True`), mostrando un spinner en la tarjeta hasta que
  llega.
- **A veces Spotify fallaba con "no hay dispositivo Connect activo" aunque
  hubiera un dispositivo disponible**: confirmado en vivo (`sp.devices()`)
  que un dispositivo Connect registrado (el PC, el móvil...) puede dejar
  de figurar como "activo" tras un rato sin usarse, y `start_playback()`
  sin indicar `device_id` falla en ese caso aunque el dispositivo siga
  ahí y funcione. Ahora, si el primer intento falla, se reintenta
  apuntando explícitamente al dispositivo cuando hay exactamente uno
  registrado (con varios, no hay forma fiable de adivinar cuál quiere el
  usuario, así que se mantiene el error de siempre).

## [0.3.0] - 2026-08-09

### Added
- **Reloj con fecha en el home**, junto a los accesos de Biblioteca/
  Spotify/Ajustes: hora y fecha con el formato regional configurado en el
  sistema (sin idioma/formato hardcodeado — `toLocaleTimeString`/
  `toLocaleDateString` sin locale explícito, heredan el idioma/región de
  Windows). Toca la hora o la fecha para verla a pantalla completa (mismo
  patrón que el VU-metro: mueve los mismos elementos al overlay, no los
  duplica).
- **Script de configuración de kiosko para Windows**
  (`scripts/setup_kiosk_windows.ps1`): automatiza los pasos de
  `docs/index.html` ("Preparar el equipo como kiosko") — inicio de sesión
  automático (si la cuenta no tiene contraseña), desactivar el
  salvapantallas/bloqueo por inactividad, y arranque automático de Kodi
  (minimizado) y Ámbar con el sistema. Se relanza solo con permisos de
  administrador (UAC) si hace falta. Modo asistente por defecto (pide
  confirmación paso a paso) o `-All` para aplicarlo todo sin preguntar.
  **Verificado en vivo end-to-end** en el equipo de desarrollo: los tres
  pasos se aplicaron correctamente y los accesos directos de Inicio
  apuntan a los ejecutables reales con el modo de ventana esperado.
- **Indicador de "Me gusta" y "Descubrimiento semanal" para pistas de
  Spotify**: junto al título de la canción, un icono ❤️/🤍 muestra si está
  en tu biblioteca de "Me gusta" y otro 📻 si está en tu playlist
  "Descubrimiento semanal"/"Discover Weekly" (buscada por nombre entre tus
  playlists, en español o inglés). Ambos son solo indicador, no botón de
  añadir: **confirmado en vivo con una sesión real y autorizada** que
  `GET /me/tracks/contains` y `PUT /me/tracks` (comprobar/añadir una pista
  suelta a "Me gusta") devuelven 403 Forbidden para esta app — restricción
  de la propia API de Spotify desde sus cambios de noviembre de 2024, que
  limita esas operaciones puntuales a apps aprobadas para "Extended Quota
  Mode"; desde mayo de 2025 Spotify solo aprueba esa extensión a
  organizaciones con 250k+ usuarios activos mensuales, no viable para un
  proyecto personal. `GET /me/tracks` (listar toda la biblioteca) sí
  funciona sin restricción, así que el indicador de "Me gusta" se resuelve
  descargando la lista completa una vez (paginada, cacheada 10 minutos en
  `SpotifyGateway`) y comparando en local, en vez de preguntar pista a
  pista. Solo se comprueba contra la API cuando cambia la canción (no en
  cada sondeo de 2s de "ahora suena"). **Dos bugs encontrados y arreglados
  al verificar en vivo con capturas reales a 1920x720**: (1) el texto
  largo de la insignia "Descubrimiento semanal" desbordaba el ancho fijo
  del layout y empujaba fuera de pantalla la columna de accesos
  (Biblioteca/Spotify/Ajustes/reloj) — acortado el texto y añadido
  `flex-wrap` de seguridad; (2) `.spotify-badges{display:flex}` ganaba
  sobre el atributo HTML `hidden` (misma prioridad de especificidad CSS,
  pero una regla de autor siempre gana a la hoja de estilos por defecto
  del navegador), así que las insignias nunca llegaban a ocultarse de
  verdad sin reproducción de Spotify — añadida la regla
  `.spotify-badges[hidden]{display:none !important;}`, mismo patrón ya
  usado para el VU-metro.
- **Identificación de CD de audio (título de álbum, artista, canciones y
  carátula)**: un CD de audio Redbook no lleva metadatos propios, así que
  Kodi solo veía "Track 01", "Track 02"... Ahora `KodiGateway` calcula la
  tabla de contenidos (TOC) del disco a partir de los tamaños de pista
  que ya da Kodi (`Files.GetDirectory`/`cdda://local/`, 2352 bytes por
  sector CD-DA) y la consulta contra la API pública de MusicBrainz (sin
  API key), igual que hacen reproductores como foobar2000/MusicBrainz
  Picard. Si encuentra coincidencia, sustituye los títulos genéricos por
  los reales en la pestaña "CD", en la lista de reproducción actual y en
  "ahora suena" (título, artista, álbum y carátula en calidad "grande",
  vía Cover Art Archive). Si el disco no está catalogado o no hay
  internet, sigue mostrando lo genérico de Kodi como hasta ahora — no
  rompe nada. Nuevo adapter `ambar/adapters/musicbrainz/gateway.py`, con
  resultado cacheado **en disco** (junto a `config.json`/`.spotify-cache`,
  sobrevive a reinicios del launcher, no solo mientras el proceso sigue
  vivo). La pestaña CD muestra una cabecera con carátula/álbum/artista y
  un botón 🔄 para forzar una nueva identificación ignorando la caché —
  útil si el disco se identificó mal, o si la primera consulta falla por
  una conexión lenta al arrancar (timeout subido de 5s a 10s tras
  confirmar en vivo un fallo así en el primer intento, resuelto al
  instante con el botón de refrescar). **Verificado en vivo** con un CD
  real: "Yo, minoría absoluta" de Extremoduro identificado
  correctamente, con sus 10 canciones y carátula, y con la config
  (`config.json`/`.spotify-cache`) preservada entre recompilaciones (ver
  más abajo, sección `build.py`).
- **Conexión con Spotify más amigable**: en Ajustes, junto a los
  campos de credenciales, un indicador de estado en vivo ("Conectado"
  / "Sin autorizar todavía", sondeado cada 3s mientras Ajustes está
  abierto) para saber si la autorización funcionó sin tener que cerrar
  Ajustes y probar a reproducir algo. Las páginas `/login` (sin
  credenciales configuradas) y `/callback` (éxito o error) pasan de
  texto plano a una página con la misma estética ámbar/gunmetal del
  resto de la app.

  **Nota sobre el redirect URI (importante):** se probó primero con un
  código QR para autorizar desde el móvil, pero **no funciona por una
  restricción real de Spotify/OAuth, no un bug**: Spotify exige HTTPS
  en el `redirect_uri` salvo para la IP de loopback literal
  `127.0.0.1` (ni `localhost` ni la IP de la LAN valen — confirmado en
  vivo: la Dashboard de Spotify rechaza `http://localhost:5005/callback`
  con "This redirect URI is not secure"). Y por cómo funciona OAuth,
  esa URI de loopback solo puede resolverse en el mismo equipo donde
  corre Ámbar: si se autoriza desde el móvil, la redirección final de
  Spotify a `127.0.0.1:5005/callback` apuntaría al propio móvil, no al
  servidor real, y la autorización nunca llegaría. `DEFAULT_SPOTIFY_REDIRECT_URI`
  pasa de `http://localhost:5005/callback` a `http://127.0.0.1:5005/callback`,
  y la autorización debe completarse en un navegador normal del mismo
  equipo (no el launcher, no otro dispositivo) — documentado así en
  Ajustes, `docs/index.html` y el registro de la app en el Dashboard
  de Spotify. El QR se retiró por completo (no tenía forma de
  funcionar dado lo anterior).
- **Navegación por álbumes**: nueva pestaña "Álbumes" en la biblioteca
  de Kodi, junto a "Artistas (Kodi)", que lista todos los álbumes
  directamente sin tener que entrar primero por un artista. Reutiliza
  `LibraryService.kodi_albums(None)` (ya soportaba listar sin filtrar
  por artista) y los mismos `renderGrid`/`renderList` del frontend.
- **Carátula de artista con sustituto**: cuando Kodi no tiene imagen
  de artista scrapeada (`thumbnail: ""`, el caso más común —
  confirmado en vivo: 692 de 2008 artistas de esta biblioteca no
  tienen imagen propia pero sí carátula de álbum), `KodiGateway.get_artists()`
  ahora usa la carátula del primer álbum de ese artista como
  sustituto, en vez de dejar el hueco vacío. Una sola llamada extra a
  `AudioLibrary.GetAlbums` (todos los álbumes de golpe), no una por
  artista.
- **Enlace de autorización de Spotify clicable**: en Ajustes, el texto
  `http://127.0.0.1:5005/login` ahora se puede pulsar directamente
  para abrirlo en el navegador del sistema (`webbrowser.open`, nuevo
  endpoint `POST /api/system/open-spotify-login`), en vez de tener que
  copiarlo a mano. Sigue una URL fija en el backend (no acepta una URL
  arbitraria del cliente) para no exponer un "abridor de URLs"
  genérico a otros dispositivos de la misma red.
- **Navegación por artista y álbum en Spotify**: además de "Listas
  (Spotify)", ahora hay pestañas "Artistas (Spotify)" (artistas
  seguidos → sus álbumes → sus canciones) y "Álbumes (Spotify)"
  (álbumes guardados → sus canciones), con "reproducir todo" en cada
  nivel. Nuevos métodos en `SpotifyGateway` (`get_followed_artists`,
  `get_artist_albums`, `get_saved_albums`, `get_album_tracks`) y rutas
  `/api/library/spotify/artists`, `/artist-albums`, `/albums`,
  `/album-tracks`. La pestaña "Álbumes" de Kodi pasa a llamarse
  "Álbumes (Kodi)" para distinguirla de la nueva de Spotify.
- **Pestañas de biblioteca filtradas por origen**: al entrar desde el
  acceso de Kodi solo se ven sus pestañas (Artistas, Álbumes, Carpetas,
  CD); al entrar desde el de Spotify, solo las suyas (Artistas,
  Álbumes, Listas). Antes se mostraban las 7 mezcladas siempre, lo que
  no dejaba claro por dónde se estaba navegando.

### Fixed
- **El equipo se bloqueaba por inactividad con Ámbar abierto**, pese al
  wake lock de Windows. Causa: `WindowsWakeLock` llamaba a
  `SetThreadExecutionState` una sola vez al arrancar — confirmado en vivo
  que no bastaba (la sesión se bloqueó igual, con el salvapantallas de
  Windows a 60s y bloqueo al reanudar activado). Ahora se reafirma cada
  30s desde un hilo de fondo, mismo patrón que usan apps tipo "Caffeine".
  **Importante**: esto no sustituye desactivar el salvapantallas/bloqueo
  por inactividad a nivel de Windows en el equipo del kiosko — ninguna
  app puede evitar de forma soportada ese bloqueo "seguro" desde fuera,
  es una protección de seguridad intencional del sistema. Nueva sección
  "Preparar el equipo como kiosko (Windows)" en `docs/index.html` con los
  pasos de configuración de Windows (inicio de sesión automático,
  desactivar salvapantallas, arranque automático de Kodi/Ámbar).
- **El VU-metro en modo "Rápido" no se notaba más vivo que "Normal".**
  Causa: `AudioLevelService` limitaba la publicación de eventos por
  WebSocket a 20/s de forma fija, igual en los tres presets de fluidez —
  aunque la ballística interna de "Rápido" ya era más ágil, el frontend
  solo veía una muestra nueva cada 50ms igual que en "Normal", así que el
  movimiento no se notaba de verdad. Ahora la frecuencia de publicación
  también escala por preset (`throttle_hz` en `VU_SMOOTHING_PRESETS`):
  30Hz en "Rápido" (antes 20Hz fijo), 20Hz en "Normal", 15Hz en "Suave".
  De paso, tiempos de ataque/liberación de "Rápido" algo más ajustados
  (0.02s/0.1s, antes 0.04s/0.15s).
- **`python build.py` borraba en silencio `config.json`/`.spotify-cache` del
  `.exe` compilado en Windows.** Causa: PyInstaller (`--clean`) borra y
  recrea `dist/Ambar/` entero en cada build, y ahí es donde vive la
  config en tiempo de ejecución en Windows (a diferencia de macOS, donde
  `_get_data_dir` ya usa la carpeta *contenedora* del `.app` precisamente
  para evitar esto). Confirmado en vivo: se perdieron credenciales de
  Spotify ya autorizadas. `build.py` ahora hace backup de
  `config.json`/`.spotify-cache`/`cd_cache.json`/`skins/` antes de
  invocar a PyInstaller y los restaura después.
- **La pestaña CD nunca se habilitaba en Windows aunque Kodi reprodujera
  el CD sin problema.** Causa: `has_audio_cd()` dependía de los
  booleanos `system.hasmediadvdaudio`/`system.hasaudiocd` de
  `XBMC.GetInfoBooleans`, y confirmado en vivo (con un CD real
  insertado en el mini PC) que ambos se quedan permanentemente en
  `False` en esta build de Kodi para Windows, aunque Kodi ya detecta el
  disco solo como fuente "G: (Audio-CD)" y `cdda://local/` devuelve las
  pistas reales sin problema — solo `system.hasmediadvd` (genérico,
  cualquier disco óptico) daba `True`. Mismo tipo de fallo ya conocido
  en macOS (ver `TODO.md`), pero con un arreglo distinto porque aquí
  `cdda://local/` sí funciona: `has_audio_cd()` ahora comprueba
  directamente si `Files.GetDirectory` sobre `cdda://local/` devuelve
  pistas, en vez de fiarse de los booleanos de estado de Kodi.
- **Control de volumen no disponible en Windows** (`WinError
  -2147417850`, "no se puede cambiar el modo de subproceso después de
  establecerlo"). Causa: `soundcard` (VU-metro) inicializa COM en modo
  multi-hilo (MTA) en el hilo principal al importarse, y `comtypes`
  (control de volumen, vía `pycaw`) inicializa COM en modo un-solo-hilo
  (STA) por defecto en cuanto se importa — Windows no permite cambiar
  el modelo de hilos COM ya establecido en un hilo
  (`RPC_E_CHANGED_MODE`). `windows_volume.py` ahora fija
  `sys.coinit_flags` a MTA antes de importar `comtypes`, para que
  coincida con el modo que `soundcard` ya deja puesto.
- **Los botones y la barra de volumen no hacían nada en Windows,
  siempre mostrando 0%** (segundo fallo distinto al anterior, tras
  arreglar el choque COM). Causa real: `pycaw` no tenía versión fijada
  en `requirements.txt`, así que se instaló una release reciente
  (`20251023`) cuya `AudioUtilities.GetSpeakers()` ya no devuelve el
  puntero COM crudo, sino un wrapper `AudioDevice` sin método
  `.Activate()` — `_endpoint_volume()` lanzaba `AttributeError` en cada
  llamada, silenciado por el `try/except` de `get()`/`set_level()`/
  `set_muted()`, así que nunca se veía el error. Arreglado usando la
  propiedad `.EndpointVolume` del wrapper (hace el
  `Activate`+`QueryInterface` por dentro) y fijada la versión de
  `pycaw` en `requirements.txt` para que no vuelva a romperse solo con
  una reinstalación. **Verificado en vivo en el mini PC real**: lectura
  del volumen real (70%), bajado a 40%, silenciado, quitado el
  silencio y restaurado a 70% sin dejar el volumen del equipo alterado.
- **Navegación por artista de Spotify daba "no hay artistas o falta
  autorizar" con artistas seguidos de verdad.** Causa real: al scope
  de OAuth (`SPOTIFY_SCOPE`) le faltaba `user-follow-read`, necesario
  para `current_user_followed_artists`; la llamada fallaba con "scope
  insuficiente", `SpotifyGateway` lo capturaba en silencio y devolvía
  lista vacía, indistinguible en el frontend de "no autorizado".
  **Requiere volver a autorizar Spotify una vez** desde Ajustes: al
  cambiar el scope solicitado, Spotipy invalida el token cacheado
  existente automáticamente (no cubre el scope nuevo) y hace falta
  reconfirmar el permiso.
- **Seleccionar un álbum o lista de Spotify a veces no reproducía
  nada, sin avisar.** `play_context`/`play_track` capturaban
  cualquier fallo de la llamada a Spotify (el más común: ningún
  dispositivo Spotify Connect activo en ese momento) y devolvían éxito
  igualmente — el frontend cerraba la biblioteca como si hubiera
  funcionado. Ahora se propaga el fallo real y se avisa con un mensaje
  explicando qué comprobar (dispositivo Connect activo, autorización
  vigente). De paso, `SpotifyGateway._client()` ya no puede lanzar una
  excepción sin capturar si falla el refresco del token de acceso
  (causaba un 500 silencioso en cualquier ruta de Spotify, incluida la
  de reproducir).
- **Las carátulas no cargaban al navegar por carpetas**: el backend ya
  pedía `thumbnail` a Kodi, pero el frontend nunca lo pintaba
  (`renderDirectoryList` solo mostraba un icono fijo). Ver también
  `TODO.md` para el matiz: Kodi normalmente no devuelve thumbnail real
  ahí porque es una ruta de filesystem fuera de la biblioteca — el fix
  pinta la imagen en cuanto Kodi la dé, pero no puede inventar datos
  que Kodi no manda.
- **A veces tardaba mucho en actualizarse el título/carátula al
  cambiar de canción.** La primera consulta a Kodi justo tras el
  evento `Player.OnPlay`/`Player.OnAVStart` a veces llegaba con
  metadatos incompletos (la carátula en particular puede tardar en
  resolverse la primera vez), y como no hay un evento nuevo para el
  mismo item, el dato desactualizado se quedaba así hasta el próximo
  cambio de estado o el sondeo de respaldo. Ahora esos dos eventos
  publican el estado dos veces (al instante y 1s después), y el
  sondeo de respaldo del frontend baja de 5s a 2s.

## [0.2.0-beta.1] - 2026-07-27

### Added
- **Imagen por defecto de "sin carátula" rediseñada**: antes un icono
  genérico de nota musical, ahora un vinilo (surcos, brillo, etiqueta
  central en ámbar) acorde a la estética "receptor HiFi vintage".
- **Botones pensados para pantalla táctil**: aumentado el tamaño de
  los botones pequeños (silenciar/volumen, abrir lista de
  reproducción, ampliar VU-metro), de 28-34px a 40-52px — por debajo
  de ~44px son incómodos de acertar con el dedo en la pantalla táctil
  real del proyecto.
- **Controles de volumen integrados directamente en el home**, en vez
  de una vista aparte que había que abrir con un icono 🔊 (`#view-volume`,
  ya retirada): fila compacta bajo el VU-metro con
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
- Documentación (`CLAUDE.md`, `.agents`, `docs/index.html`) ya no
  menciona el addon Chorus2 para la vista de biblioteca — quedó
  obsoleto desde que la navegación de artistas/álbumes/canciones/
  carpetas/CD se implementó de forma nativa contra la API JSON-RPC de
  Kodi, sin iframe ni webinterface externo.

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
- **Los botones de transporte (⏮/⏯/⏭) no estaban centrados** —
  `.transport` no tenía `justify-content`, así que quedaban pegados a
  la izquierda del panel en vez de centrados.
- **Iconos de volumen repetidos y poco descriptivos**: 🔊 se usaba a
  la vez para "subir volumen" y para el estado "sin silenciar" del
  botón de silenciar, indistinguibles entre sí. Ahora son tres iconos
  distintos: 🔈 (silenciar) / 🔇 (silenciado) para el botón de mute,
  🔉 para bajar, 🔊 para subir.
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

[Unreleased]: https://github.com/laralbir/ambar-kodi-launcher/compare/v0.2.0-beta.1...HEAD
[0.2.0-beta.1]: https://github.com/laralbir/ambar-kodi-launcher/compare/v0.1.0...v0.2.0-beta.1
[0.1.0]: https://github.com/laralbir/ambar-kodi-launcher/releases/tag/v0.1.0
