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
