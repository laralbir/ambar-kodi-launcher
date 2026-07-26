import json
import threading
import time

import websocket

from ambar.adapters.kodi.gateway import KodiGateway
from ambar.application.now_playing import NowPlayingService


def listen(gateway: KodiGateway, now_playing_service: NowPlayingService) -> None:
    """Escucha el WebSocket de eventos de Kodi y publica el estado en cada cambio.

    Se reconecta cada 5s si Kodi no esta disponible.
    """
    while True:
        try:
            ws = websocket.WebSocket()
            ws.connect(gateway.ws_url, timeout=3)
            _publish_async(now_playing_service)
            while True:
                msg = ws.recv()
                if msg:
                    data = json.loads(msg)
                    method = data.get("method", "")
                    if method.startswith("Player.On") or method == "Playlist.OnAdd":
                        _publish_async(now_playing_service)
        except Exception:
            time.sleep(5)


def _publish_async(now_playing_service: NowPlayingService) -> None:
    # No bloquear el bucle de recv() mientras se consulta el estado.
    threading.Thread(target=now_playing_service.publish_current_state, daemon=True).start()
