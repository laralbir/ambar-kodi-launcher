import time

from ambar.application.now_playing import NowPlayingService


def poll(now_playing_service: NowPlayingService) -> None:
    """Sondea Spotify cada 3s (para no abusar de la API) mientras Kodi no sea la
    ultima fuente activa conocida."""
    while True:
        try:
            now_playing_service.poll_spotify()
        except Exception:
            pass
        time.sleep(3)
