import os
import sys
import webbrowser

from ambar.application.audio_level import AudioLevelService
from ambar.ports.window_controller import WindowController


class SystemService:
    """Comandos de sistema del kiosko: pantalla completa, salir, apagar, reiniciar."""

    def __init__(
        self,
        window: WindowController,
        audio_level_service: AudioLevelService,
        volume_controller,
        kodi_gateway,
        spotify_gateway,
        screen_wake_lock,
    ):
        self._window = window
        self._audio_level_service = audio_level_service
        self._volume_controller = volume_controller
        self._kodi_gateway = kodi_gateway
        self._spotify_gateway = spotify_gateway
        self._screen_wake_lock = screen_wake_lock

    def start(self) -> None:
        # Evitar que la pantalla se apague/salte el salvapantallas/el equipo
        # entre en reposo mientras Ambar esta en ejecucion -- un kiosko se
        # supone siempre visible.
        self._screen_wake_lock.acquire()

    def get_volume(self) -> dict:
        return self._volume_controller.get()

    def set_volume_level(self, level: int) -> None:
        self._volume_controller.set_level(level)

    def set_volume_muted(self, muted: bool) -> None:
        self._volume_controller.set_muted(muted)

    def secure_cursor(self) -> None:
        """Fija el cursor del ratón del sistema en un único punto (esquina
        superior izquierda de la ventana de Ámbar, con un margen mínimo)
        y le devuelve el foco de Windows -- pensado para el mando (JZK
        G20S Pro): en "air mode" mueve el puntero de verdad al mover el
        mando en el aire, y tanto OK como Atrás, confirmado en vivo, son
        clics de ratón reales (izquierdo/derecho) en la posición del
        cursor, no teclas. Sin esto, el aire-ratón podía sacar el cursor a
        otro monitor (la TV, en un equipo con más de uno) -- lo que le
        quitaba a Ámbar el foco de Windows por completo, dejando de
        llegarle hasta el teclado real -- o, dentro de la propia ventana,
        moverlo (oculto, no se ve dónde queda) encima de cualquier
        tarjeta/botón real, disparando una acción no deseada.

        `ClipCursor` sobre un rectángulo de un único píxel, no sobre toda
        la ventana: se probó a confinar solo dentro de los límites de la
        ventana (dejando moverse con libertad por dentro), y en vivo
        seguía dando clics falsos -- basta con mover el mando en el aire
        entre una flecha y la pulsación de OK/Atrás para que el cursor ya
        se haya desplazado a otro punto de la ventana. Con el rectángulo
        reducido a un solo píxel, físicamente no puede moverse ni un
        pixel de ahí, se mueva como se mueva el mando.

        Windows libera el confinamiento él solo si Ámbar pierde el foco
        (p.ej. si se abre otra ventana por encima), así que no deja el
        cursor bloqueado para siempre si algo falla -- por eso también se
        vuelve a aplicar en cada movimiento del D-pad (ver
        /api/system/secure-cursor), no solo una vez al arrancar.

        Coordenadas ABSOLUTAS ancladas a `webview.windows[0].x/y` (la
        posición real de la ventana), no un desplazamiento relativo sin
        límite: una primera versión con desplazamiento relativo enorme
        (pensando que Windows lo recortaría sola al borde de la pantalla)
        se probó y se quitó -- confirmado en vivo que cruzaba al otro
        monitor igualmente. `SetForegroundWindow` en vez de simular un
        clic para recuperar el foco: un clic sintético en cada movimiento
        del D-pad activaría el elemento con foco sin querer,
        confundiéndose con un OK real.

        Solo Windows; best-effort (si `webview` no está disponible o
        falla, no rompe nada más)."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            import webview

            if not webview.windows:
                return
            win = webview.windows[0]
            x, y = int(win.x) + 2, int(win.y) + 2
            rect = wintypes.RECT(x, y, x + 1, y + 1)
            ctypes.windll.user32.ClipCursor(ctypes.byref(rect))
            ctypes.windll.user32.SetCursorPos(x, y)
            hwnd = ctypes.windll.user32.FindWindowW(None, "Ámbar")
            if hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def open_spotify_login(self) -> None:
        """Abre /login en el navegador del sistema (no en el propio webview
        del kiosko, que no puede completar el flujo OAuth de forma fiable --
        ver CHANGELOG.md/TODO.md). URL fija, no aceptamos una URL arbitraria
        del cliente para no exponer un "abridor de URLs" generico a quien
        sea que esté en la misma red."""
        try:
            webbrowser.open("http://127.0.0.1:5005/login")
        except Exception:
            pass

    def execute(self, action: str | None) -> None:
        if action == "fullscreen":
            self._window.toggle_fullscreen()
        elif action == "exit":
            # Parar la reproduccion actual (Kodi/Spotify, lo que este sonando)
            # antes de cerrar -- si no, el audio se queda sonando aunque el
            # launcher ya no este. Ambas llamadas son best-effort (no lanzan
            # si esa fuente no esta activa/configurada).
            self._kodi_gateway.stop()
            self._spotify_gateway.pause()
            self._screen_wake_lock.release()
            # Parar la captura de audio ANTES de cerrar la ventana: si el
            # proceso empieza a apagarse mientras ScreenCaptureKit sigue
            # disparando callbacks nativos de ObjC en un hilo de fondo, el
            # interprete puede reventar al finalizar (crash visible como
            # "Ambar-x se ha cerrado inesperadamente" en macOS).
            self._audio_level_service.stop()
            self._window.close()
        elif action == "shutdown":
            os.system("shutdown /s /t 0" if sys.platform == "win32" else "sudo shutdown -h now")
        elif action == "restart":
            os.system("shutdown /r /t 0" if sys.platform == "win32" else "sudo shutdown -r now")
