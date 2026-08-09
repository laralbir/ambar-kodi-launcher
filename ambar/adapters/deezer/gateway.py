import requests

USER_AGENT = "AmbarKodiLauncher/0.3 ( https://github.com/laralbir/ambar-kodi-launcher )"


class DeezerGateway:
    """Respaldo gratuito y sin autenticacion para fotos de artista, cuando
    Spotify no esta configurado/autorizado o no encuentra el artista (ver
    SpotifyGateway.find_artist_image, que se prueba primero -- ya
    autorizado, se usa con preferencia). API publica de Deezer, sin API
    key ni cuenta.

    Cacheado en memoria por nombre en minusculas, igual que el fallback de
    Spotify -- no hace falta persistir en disco."""

    def __init__(self):
        self._cache: dict[str, str | None] = {}

    def find_artist_image(self, name: str) -> str | None:
        if not name:
            return None
        key = name.strip().lower()
        if key in self._cache:
            return self._cache[key]
        image = self._lookup(name)
        self._cache[key] = image
        return image

    def _lookup(self, name: str) -> str | None:
        try:
            r = requests.get(
                "https://api.deezer.com/search/artist",
                params={"q": name, "limit": 10},
                headers={"User-Agent": USER_AGENT},
                timeout=10,
            )
            data = r.json()
        except Exception:
            return None
        # Deezer no puntua relevancia como MusicBrainz/Spotify -- de los
        # resultados con nombre exacto (sin distinguir mayusculas), se
        # queda con el de mas fans, que es el artista real casi siempre
        # (evita coincidencias como "Erasure (US)", una banda tributo con
        # pocos fans, ganando al Erasure real).
        candidates = [
            a for a in (data.get("data") or [])
            if a.get("name", "").strip().lower() == name.strip().lower()
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda a: a.get("nb_fan", 0))
        return best.get("picture_medium") or best.get("picture") or None
