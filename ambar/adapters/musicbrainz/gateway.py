import json
import os

import requests

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/discid/-"
# "-1200" (lado grande de Cover Art Archive, tipicamente 1200px) en vez del
# thumbnail "-250" original: bastante mas nitida en la caratula grande del
# launcher (82vh en la pantalla panoramica) sin tirar de la imagen a
# resolucion completa, que puede pesar varios MB.
COVER_ART_URL = "https://coverartarchive.org/release/{mbid}/front-1200"
USER_AGENT = "AmbarKodiLauncher/0.2 ( https://github.com/laralbir/ambar-kodi-launcher )"


class MusicBrainzGateway:
    """Identifica el CD de audio insertado contra MusicBrainz a partir de
    su tabla de contenidos (TOC) -- titulo de album, artista, lista de
    canciones y caratula (via Cover Art Archive, sin API key). Un CD de
    audio Redbook no lleva metadatos propios (por eso Kodi solo ve "Track
    01", "Track 02"...); este es el mismo mecanismo que usan reproductores
    como foobar2000/MusicBrainz Picard para identificarlo, sin depender de
    una libreria nativa (libdiscid) -- el TOC ya lo calcula KodiGateway a
    partir de los tamaños de pista que da Kodi.

    Se usa la busqueda por TOC (?toc=...) en vez de calcular el DiscID
    exacto (SHA1+base64) a mano: acepta pequeñas diferencias de offset
    entre prensados/lecturas del mismo disco, que son la norma (unos
    pocos sectores por pista), y devuelve varios candidatos entre los que
    hay que elegir el mas cercano -- ver _best_match.

    Resultado cacheado en disco (cache_path, un JSON en el mismo directorio
    de datos que config.json/.spotify-cache -- ver ambar/bootstrap.py),
    clave = TOC exacto: sobrevive a reinicios del launcher, para no repetir
    la consulta de red cada vez que se vuelve a poner el mismo CD."""

    def __init__(self, cache_path: str | None = None):
        self._cache_path = cache_path
        self._cache: dict[str, dict | None] = self._load_cache()
        self._last: dict | None = None

    def _load_cache(self) -> dict:
        if not self._cache_path or not os.path.exists(self._cache_path):
            return {}
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cache(self) -> None:
        if not self._cache_path:
            return
        try:
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False)
        except Exception:
            pass

    @staticmethod
    def _key(toc: list[int]) -> str:
        return ",".join(str(n) for n in toc)

    def get_last(self) -> dict | None:
        """Ultimo resultado identificado con exito, sin tocar la cache ni
        la red -- para el estado de "ahora suena" (sondeado cada 2s), que
        no puede permitirse esperar a una consulta HTTP en cada vuelta."""
        return self._last

    def identify(self, toc: list[int], force: bool = False) -> dict | None:
        """force=True ignora la cache (en disco y en memoria) y repite la
        consulta -- para el boton "actualizar" del CD tab del frontend,
        util si el disco se identifico mal o se puso otro CD sin que el
        TOC cambiara lo suficiente para notarlo por si solo."""
        key = self._key(toc)
        if not force and key in self._cache:
            result = self._cache[key]
        else:
            result = self._lookup(toc)
            self._cache[key] = result
            self._save_cache()
        if result:
            self._last = result
        return result

    def _lookup(self, toc: list[int]) -> dict | None:
        try:
            r = requests.get(
                MUSICBRAINZ_URL,
                params={
                    "toc": " ".join(str(n) for n in toc),
                    "fmt": "json",
                    "inc": "recordings+artist-credits",
                },
                headers={"User-Agent": USER_AGENT},
                # 10s, no 5: confirmado en vivo que la primera consulta del
                # proceso (DNS/TLS en frio) puede tardar mas que un timeout
                # corto y fallar sin necesidad -- se cachea igual como "no
                # encontrado" (ver identify) hasta que se fuerce un reintento.
                timeout=10,
            )
            data = r.json()
        except Exception:
            return None
        match = self._best_match(data.get("releases") or [], toc[3:])
        if not match:
            return None
        release, medium = match
        artist = "".join(
            (c.get("name", "") + c.get("joinphrase", "")) for c in release.get("artist-credit", [])
        ).strip()
        tracks = [
            t.get("title", "")
            for t in sorted(medium.get("tracks", []), key=lambda t: t.get("position", 0))
        ]
        art = None
        if release.get("cover-art-archive", {}).get("front"):
            art = COVER_ART_URL.format(mbid=release["id"])
        return {
            "title": release.get("title") or "",
            "artist": artist,
            "tracks": tracks,
            "art": art,
        }

    @staticmethod
    def _best_match(releases: list, our_offsets: list[int]):
        """De entre todas las coincidencias aproximadas que devuelve la
        busqueda por TOC, elige el disco cuyos offsets de pista esten mas
        cerca de los reales -- confirmado en vivo que candidatos con
        cientos/miles de sectores de diferencia por pista son prensados o
        relanzamientos distintos, no el disco insertado (una diferencia de
        unas pocas decenas de sectores por pista si es normal, variacion
        de lectura/grabacion)."""
        best = None
        best_score = None
        for release in releases:
            for medium in release.get("media", []):
                if medium.get("track-count") != len(our_offsets):
                    continue
                for disc in medium.get("discs", []):
                    offsets = disc.get("offsets") or []
                    if len(offsets) != len(our_offsets):
                        continue
                    score = sum(abs(a - b) for a, b in zip(offsets, our_offsets))
                    if best_score is None or score < best_score:
                        best_score = score
                        best = (release, medium)
        return best
