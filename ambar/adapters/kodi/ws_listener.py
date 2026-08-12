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
                    if method in ("Player.OnPlay", "Player.OnAVStart"):
                        # Cambio de pista: la primera consulta a Kodi justo
                        # tras el evento a veces llega con metadatos
                        # incompletos (la caratula en particular puede
                        # tardar en resolverse la primera vez que se pide
                        # su thumbnail) -- se repite una vez mas tras una
                        # breve espera en vez de dejar el titulo/caratula
                        # desactualizados hasta el siguiente evento o el
                        # sondeo de respaldo del frontend.
                        _publish_async(now_playing_service)
                        _publish_delayed(now_playing_service, 1.0)
                        # NOTA: enforce_single_source() (pausar Spotify si
                        # tambien estaba sonando) se probo aqui tambien,
                        # en reaccion inmediata a este evento -- pero
                        # lanzaba una consulta a Spotify (SMTC) mas justo
                        # cuando Kodi esta mas ocupado arrancando una
                        # pista, y se noto como lentitud navegando por
                        # Kodi. Se quito: el sondeo periodico (cada 3s,
                        # ver adapters/spotify/poller.py) ya cubre esto
                        # sin competir por recursos en el peor momento.
                    elif method.startswith("Player.On") or method == "Playlist.OnAdd":
                        _publish_async(now_playing_service)
        except Exception:
            time.sleep(5)


def _publish_async(now_playing_service: NowPlayingService) -> None:
    # No bloquear el bucle de recv() mientras se consulta el estado.
    threading.Thread(target=now_playing_service.publish_current_state, daemon=True).start()


def _publish_delayed(now_playing_service: NowPlayingService, delay_seconds: float) -> None:
    def _run():
        time.sleep(delay_seconds)
        now_playing_service.publish_current_state()
    threading.Thread(target=_run, daemon=True).start()
