# Ámbar — contexto del proyecto

Nombre del proyecto: **Ámbar**, por el acento ámbar tipo display
VFD/LED que define la estética del launcher.

Panel táctil para una estación multimedia HiFi (mini PC + amplificador
Pioneer SA-508), pensado para vivir en `/Users/carlos/Projects/hifi-codi-launcher`.

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
- `kiosk_server.py` — servidor Flask (API + estático).
- `.spotify-cache` — se genera solo tras autorizar Spotify (no versionar).

## Pendiente / próximos pasos

- Configurar credenciales de Spotify Developer Dashboard
  (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`) y autorizar una vez
  vía `/login`.
- Posibles ajustes de diseño (tamaños, colores) a petición de Carlos.
- Añadir `requirements.txt` / README de instalación si se pide.
- Validar en la pantalla táctil real el layout panorámico bajo.
