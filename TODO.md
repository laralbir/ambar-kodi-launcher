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
  `README.md` y `docs/index.html` mientras tanto. Ya se estabilizaron
  `--osx-bundle-identifier` y el nombre del binario (`Ambar`, sin
  versión) para reducir cuánto cambia entre builds — la firma ad-hoc
  en sí sigue siendo la causa raíz que falta arreglar del todo.
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
- Lista de reproducción actual visible en el home: da igual si viene
  de un artista, álbum, carpeta, CD o de Spotify, debe mostrarse la
  lista completa (no solo la pista actual) con la canción en curso
  resaltada. La lista se puede ocultar/mostrar, y ese estado
  (visible/oculta) debe persistir entre sesiones (como el resto de
  ajustes, vía `config.json`/`/api/config`).
- Marquee (desplazamiento lateral) para título/artista/álbum cuando el
  texto no cabe y se corta (`text-overflow:ellipsis` actual en
  `.track-title`/`.track-meta`): que se desplace lateralmente hasta
  leerse entero, con una pausa inicial antes de empezar a moverse,
  como en los displays de las autorradios.

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
