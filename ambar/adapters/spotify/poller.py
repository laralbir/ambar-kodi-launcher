import time

from ambar.application.now_playing import NowPlayingService


def poll(now_playing_service: NowPlayingService) -> None:
    """Sondea Spotify cada 3s: publica su estado (solo si Kodi no es la
    fuente activa, ver poll_spotify) y ademas comprueba si hay que pausar
    una fuente porque la otra acaba de empezar a sonar por su cuenta (ver
    enforce_single_source) -- esto ultimo se comprueba siempre, sea cual
    sea la fuente activa, para detectar tambien cuando Spotify empieza a
    sonar mientras Kodi estaba activo."""
    while True:
        try:
            now_playing_service.poll_spotify()
            now_playing_service.enforce_single_source()
        except Exception:
            pass
        time.sleep(3)
