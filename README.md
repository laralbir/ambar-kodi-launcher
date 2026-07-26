# Ámbar Kodi Launcher

Ámbar es un launcher de pantalla táctil diseñado para una estación multimedia HiFi. Permite controlar de forma centralizada la reproducción local (FLAC, MP3, CD de audio) a través de **Kodi** y la reproducción en streaming mediante **Spotify Connect**.

La interfaz gráfica está diseñada explícitamente para una pantalla secundaria táctil con una resolución panorámica baja (formato "stretched bar" de **1920x720**), utilizando una estética de receptor HiFi vintage (paneles gunmetal y acentos de color ámbar tipo VFD/LED).

📖 **[Ver el Manual de Usuario y Configuración](https://laralbir.github.io/ambar-kodi-launcher/)**

---

## Arquitectura

El proyecto consta de:
- **Frontend (UI):** Vanilla HTML/CSS/JS (`index.html`).
- **Backend:** Servidor local ligero escrito en Python (`kiosk_server.py`) usando Flask. Este backend se comunica con Kodi (vía JSON-RPC) y Spotify (vía la API Spotipy) para evitar problemas de CORS y consolidar el estado de reproducción.
- **Empaquetado:** Mediante `pywebview` y `pyinstaller`, la aplicación web se envuelve en una ventana nativa de sistema operativo sin bordes, que puede compilarse en un ejecutable independiente (como un `.exe` de Windows).

---

## Entorno de Desarrollo

Para ejecutar y modificar Ámbar de forma local en tu máquina de desarrollo (Windows o macOS):

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/laralbir/ambar-kodi-launcher.git
   cd ambar-kodi-launcher
   ```

2. **Crear y activar un entorno virtual (opcional pero recomendado):**
   ```bash
   # En Windows
   python -m venv venv
   venv\Scripts\activate
   
   # En macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Ejecutar el servidor local:**
   ```bash
   python kiosk_server.py
   ```
   *Nota: Por defecto, esto abrirá la ventana nativa de la aplicación de escritorio. Si deseas desarrollar sobre el navegador y omitir la ventana nativa, puedes ejecutar `python kiosk_server.py --no-window` y abrir `http://localhost:5005` en tu navegador.*

---

## Cómo Compilar el Ejecutable

Puedes compilar Ámbar como una aplicación independiente (`.exe` en Windows o `.app` en macOS) para que pueda arrancar en tu Mini PC kiosko sin necesidad de instalar Python ni arrancar un servidor manualmente.

> **Importante:** PyInstaller genera el binario para el sistema operativo en el que se ejecuta. Si necesitas un `.exe` para Windows 11, **debes correr estos pasos desde una máquina Windows**.

1. Asegúrate de haber instalado las dependencias en tu entorno virtual:
   ```bash
   pip install -r requirements.txt
   ```
2. Ejecuta el script de automatización de compilación:
   ```bash
   python build.py
   ```
3. Al terminar, encontrarás el binario compilado dentro de la carpeta `dist/`. Puedes llevarte esa carpeta o el ejecutable a tu kiosko multimedia.

### VU-metro en macOS: permiso de Grabación de pantalla

El VU-metro captura el audio real del sistema vía `ScreenCaptureKit`, que requiere el permiso "Grabación de pantalla y del audio del sistema" (Ajustes del Sistema → Privacidad y Seguridad). Al compilar con `python build.py` la app queda firmada de forma *ad-hoc* (sin certificado de Apple Developer), lo que provoca dos comportamientos conocidos de macOS que **no tienen solución desde el código de la app**:

- **La app no siempre aparece sola en la lista de permisos.** Si al ejecutar la app y conceder el permiso no se añade automáticamente, añádela a mano con el botón **"+"** de esa lista, navegando hasta `Ambar-X.Y.Z.app` dentro de `dist/`.
- **El permiso puede perderse en cada recompilación.** Como la firma ad-hoc cambia con cada `python build.py`, macOS puede tratar cada build como una app distinta y pedir el permiso de nuevo. Tras conceder el permiso hay que **cerrar del todo y volver a abrir la app** (no basta con que ya estuviera corriendo).

Si esto resulta demasiado incómodo para uso diario, la solución definitiva es firmar la app con un certificado de código estable (local o de Apple Developer) para que la identidad no cambie entre compilaciones — no implementado todavía, ver `TODO.md`.

---

## Versionado y releases

El número de versión vive en un único sitio: el fichero [`VERSION`](VERSION) (versionado semántico, sin la `v` inicial). `build.py` lo lee para nombrar el ejecutable generado.

Para publicar una nueva release:

1. Actualiza `VERSION` (p. ej. `0.2.0`) y añade una entrada en [`CHANGELOG.md`](CHANGELOG.md) bajo esa versión.
2. Haz commit de ambos cambios.
3. Crea y empuja un tag `vX.Y.Z` que coincida con `VERSION`:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
4. El workflow de GitHub Actions [`release.yml`](.github/workflows/release.yml) construye el ejecutable para Windows y macOS con PyInstaller y publica automáticamente una release en GitHub con ambos `.zip` adjuntos.
