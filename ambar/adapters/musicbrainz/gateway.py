import json
import os
import threading

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
        # TOC (clave, ver _key) del disco al que corresponde _last -- sin
        # esto, get_last() seguia devolviendo los metadatos del CD
        # ANTERIOR indefinidamente tras cambiar de disco (confirmado en
        # vivo: titulo/artista/caratula/pistas se quedaban pegados al CD
        # que sonara justo antes al reproducirse uno nuevo de forma
        # automatica, ver KodiGateway._enrich_cd_now_playing y
        # CHANGELOG.md). _last en si no se limpia al cambiar de disco (no
        # hay forma de detectar la expulsion desde aqui), se compara
        # contra este TOC cada vez para saber si sigue siendo valido.
        self._last_toc_key: str | None = None
        # TOCs con una identificacion de fondo ya en marcha (ver
        # identify_async) -- evita lanzar un hilo nuevo en cada sondeo de
        # "ahora suena" (cada 2s) mientras la consulta anterior sigue en
        # vuelo.
        self._refreshing: set[str] = set()

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
        no puede permitirse esperar a una consulta HTTP en cada vuelta.

        OJO: no valida que corresponda al disco insertado ahora mismo --
        usar get_last_for(toc) en su lugar salvo que ya se sepa por otro
        lado que el TOC no ha podido cambiar."""
        return self._last

    def get_last_for(self, toc: list[int]) -> dict | None:
        """Como get_last(), pero solo si el ultimo resultado corresponde
        al TOC indicado -- el del disco que esta sonando ahora mismo. Sin
        esto, tras cambiar de CD (o al arrancar una reproduccion
        automatica de uno nuevo, ver audiocds.autoaction) se seguian
        mostrando indefinidamente el titulo/artista/caratula/pistas del
        CD anterior en "ahora suena": _last no se limpiaba solo al sacar
        un disco y meter otro, y el sondeo de "ahora suena" solo dispara
        una nueva identificacion (identify_async) cuando get_last()
        viene vacio -- cosa que nunca pasaba si ya habia CUALQUIER disco
        identificado con exito antes en esta misma ejecucion."""
        if self._last is not None and self._last_toc_key == self._key(toc):
            return self._last
        return None

    def identify(self, toc: list[int], force: bool = False) -> dict | None:
        """force=True ignora la cache (en disco y en memoria) y repite la
        consulta -- para el boton "actualizar" del CD tab del frontend,
        util si el disco se identifico mal o se puso otro CD sin que el
        TOC cambiara lo suficiente para notarlo por si solo.

        Un resultado negativo (no encontrado) NO se guarda en la cache:
        confirmado en vivo que la primera consulta de un CD puede fallar
        por una conexion lenta al arrancar, y antes eso se quedaba
        "atascado" mostrando los nombres genericos de Kodi para siempre
        hasta que alguien pulsaba el boton de actualizar a mano. Sin
        cachear el fallo, el siguiente intento (ver identify_async) lo
        vuelve a intentar solo."""
        key = self._key(toc)
        if not force and key in self._cache:
            result = self._cache[key]
        else:
            result = self._lookup(toc)
            if result:
                self._cache[key] = result
                self._save_cache()
        if result:
            self._last = result
            self._last_toc_key = key
        return result

    def identify_async(self, toc: list[int]) -> None:
        """Lanza identify() en un hilo de fondo si no hay ya uno en marcha
        para este TOC -- para el sondeo de "ahora suena" (cada 2s), que no
        puede esperar a una consulta HTTP pero si quiere auto-recuperarse
        sola cuando get_last() esta vacio (disco aun no identificado, o la
        identificacion anterior fallo)."""
        key = self._key(toc)
        if key in self._refreshing:
            return
        self._refreshing.add(key)

        def _run():
            try:
                self.identify(toc)
            finally:
                self._refreshing.discard(key)

        threading.Thread(target=_run, daemon=True).start()

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
        title = release.get("title") or ""
        art = None
        if release.get("cover-art-archive", {}).get("front"):
            art = COVER_ART_URL.format(mbid=release["id"])
        if not art and artist and title:
            # La busqueda por TOC elige el "release" (edicion/prensado)
            # concreto mas parecido en offsets de pista, sin tener en
            # cuenta si esa edicion en concreto tiene caratula subida a
            # Cover Art Archive -- confirmado en vivo que un disco real
            # se identificaba bien (titulo/artista/pistas correctos) pero
            # se quedaba sin caratula porque la edicion exacta encontrada
            # no la tenia, aunque el mismo album SI la tuviera en otra
            # edicion. _lookup_album_art busca por texto en vez de TOC y
            # prueba varios candidatos hasta encontrar uno con caratula
            # de verdad -- no importa que sea de una edicion distinta a
            # la identificada, es la misma portada de todas formas.
            art = self._lookup_album_art(artist, title)
        return {
            "title": title,
            "artist": artist,
            "tracks": tracks,
            "art": art,
        }

    def find_album_art(self, artist: str, album: str, force: bool = False) -> str | None:
        """Busca la caratula de un album por texto (artista+titulo) cuando
        Kodi no tiene una propia -- misma idea que identify() para CDs, pero
        por busqueda de texto en vez de TOC (no hay tabla de contenidos que
        calcular aqui, solo el nombre). Cacheado en disco igual que
        identify(), clave = "album:<artista>|<album>" en minusculas.

        force=True ignora la cache y repite la busqueda -- para el click en
        la caratula de "ahora suena" (ver art-frame en index.html): sin
        esto, un primer intento fallido (p.ej. mala conexion al arrancar)
        se quedaba cacheado como "sin caratula" para siempre, igual que le
        pasaba a identify() con los CDs antes de tener su propio force."""
        if not artist or not album:
            return None
        key = f"album:{artist.strip().lower()}|{album.strip().lower()}"
        if not force and key in self._cache:
            return self._cache[key]
        art = self._lookup_album_art(artist, album)
        self._cache[key] = art
        self._save_cache()
        return art

    def get_cached_album_art(self, artist: str, album: str) -> str | None:
        """Como find_album_art, pero SOLO consulta la cache en disco, sin
        red -- para el sondeo de "ahora suena" (cada 2s), que no puede
        esperar a una consulta HTTP. Ver KodiGateway.get_state(): si el
        album de la pista en curso no tiene caratula propia en Kodi, se
        usa esto para no dejar el hueco vacio si ya se encontro antes
        (p.ej. al hacer click en la caratula, ver art-frame en
        index.html, que si fuerza la busqueda de red via find_album_art)."""
        if not artist or not album:
            return None
        key = f"album:{artist.strip().lower()}|{album.strip().lower()}"
        return self._cache.get(key)

    def _lookup_album_art(self, artist: str, album: str) -> str | None:
        try:
            r = requests.get(
                "https://musicbrainz.org/ws/2/release/",
                params={
                    "query": f'artist:"{artist}" AND release:"{album}"',
                    "fmt": "json",
                    "limit": 5,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=10,
            )
            data = r.json()
        except Exception:
            return None
        # La busqueda de texto (a diferencia de la busqueda por TOC de
        # identify()) no incluye si Cover Art Archive tiene imagen -- hay
        # que comprobarlo aparte. Solo se prueban resultados con score alto
        # (coincidencia de texto casi exacta, 0-100 lo da la propia API) y
        # se para en el primero que de verdad tenga caratula.
        for release in data.get("releases") or []:
            if (release.get("score") or 0) < 90:
                continue
            mbid = release.get("id")
            if mbid and self._has_cover_art(mbid):
                return COVER_ART_URL.format(mbid=mbid)
        return None

    @staticmethod
    def _has_cover_art(mbid: str) -> bool:
        try:
            r = requests.head(
                COVER_ART_URL.format(mbid=mbid),
                headers={"User-Agent": USER_AGENT},
                timeout=5,
                allow_redirects=True,
            )
            return r.status_code == 200
        except Exception:
            return False

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
