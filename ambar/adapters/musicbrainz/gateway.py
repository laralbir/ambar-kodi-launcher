import requests

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/discid/-"
COVER_ART_URL = "https://coverartarchive.org/release/{mbid}/front-250"
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

    Resultado cacheado en memoria por proceso (clave = TOC exacto), para
    no repetir la consulta de red mientras el mismo CD siga insertado."""

    def __init__(self):
        self._cache: dict[tuple, dict | None] = {}
        self._last: dict | None = None

    def get_last(self) -> dict | None:
        """Ultimo resultado identificado con exito, sin tocar la cache ni
        la red -- para el estado de "ahora suena" (sondeado cada 2s), que
        no puede permitirse esperar a una consulta HTTP en cada vuelta."""
        return self._last

    def identify(self, toc: list[int]) -> dict | None:
        key = tuple(toc)
        if key in self._cache:
            result = self._cache[key]
        else:
            result = self._lookup(toc)
            self._cache[key] = result
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
                timeout=5,
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
