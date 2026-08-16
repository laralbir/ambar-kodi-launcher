import time

from ambar.domain.playback import PlaybackState

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False


SPOTIFY_SCOPE = (
    "user-read-playback-state user-modify-playback-state "
    "playlist-read-private playlist-read-collaborative user-library-read "
    "user-follow-read user-library-modify"
)

# Nombre de la playlist algoritmica "semanal" de Spotify -- no tiene un ID
# fijo/universal (es propia de cada usuario), asi que se busca por nombre
# entre las playlists que sigue el usuario. En ingles y español (Spotify
# localiza el nombre segun el idioma de la cuenta); si en el futuro hace
# falta otro idioma, añadir aqui su traduccion.
WEEKLY_PLAYLIST_NAMES = {"discover weekly", "descubrimiento semanal"}


class SpotifyGateway:
    """Adapter hacia la Web API de Spotify (Spotipy). Se reconfigura en caliente
    cuando cambian las credenciales en Ajustes."""

    # Spotify usa "off"/"track"/"context" para repetir; el resto de la app
    # (Kodi, PlaybackState) usa "off"/"one"/"all" -- Kodi lo hace de forma
    # nativa, asi que ese es el vocabulario comun elegido, y aqui se
    # traduce en los dos sentidos.
    _REPEAT_FROM_SPOTIFY = {"off": "off", "track": "one", "context": "all"}
    _REPEAT_CYCLE = {"off": "context", "context": "track", "track": "off"}

    def __init__(self, cache_path: str, smtc_gateway=None):
        self._cache_path = cache_path
        self._oauth: "SpotifyOAuth | None" = None
        # SMTC (Windows.Media.Control) -- alternativa local, sin limite de
        # peticiones, a get_state/control/seek/pause cuando el Spotify de
        # escritorio esta sonando en esta misma maquina (ver
        # ambar/adapters/media_session/windows_smtc.py). Opcional: en
        # macOS (desarrollo) o si no se inyecta, estos metodos siguen
        # usando la Web API como hasta ahora.
        self._smtc = smtc_gateway
        # ID de la playlist "Descubrimiento semanal"/"Discover Weekly" del
        # usuario -- estable entre semanas (solo cambia el contenido, no el
        # ID), asi que una vez encontrada se cachea en memoria y no hace
        # falta volver a buscarla por nombre en cada comprobacion.
        self._weekly_playlist_id: str | None = None
        # Cache de IDs de canciones en "Me gusta" (ver _get_liked_track_ids
        # mas abajo, seccion "Me gusta"/Descubrimiento semanal).
        self._liked_track_ids: set | None = None
        self._liked_track_ids_fetched_at: float = 0.0
        # Fotos de artista encontradas por nombre, para cuando Kodi no tiene
        # ninguna propia (ver find_artist_image) -- cacheadas en memoria por
        # nombre en minusculas, no hace falta persistir en disco (se
        # recalculan solas si se reinicia el launcher, coste bajo).
        self._artist_image_cache: dict[str, str | None] = {}
        # Marca de tiempo (epoch) hasta la que Spotify ha dicho que hay que
        # esperar (cabecera Retry-After de un 429 "rate limit") -- ver
        # _record_rate_limit. 0 = no se sabe de ningun limite activo.
        self._rate_limited_until: float = 0.0

    def configure(self, client_id: str | None, client_secret: str | None, redirect_uri: str) -> None:
        if SPOTIPY_AVAILABLE and client_id and client_secret:
            self._oauth = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=SPOTIFY_SCOPE,
                cache_path=self._cache_path,
                open_browser=False,
                # Bug real de spotipy: Spotify(...) (el cliente normal) SI
                # tiene un requests_timeout por defecto (5s), pero
                # SpotifyOAuth NO -- su valor por defecto es None, sin
                # limite. get_cached_token() refresca el token contra
                # accounts.spotify.com por debajo cuando ha caducado, y esa
                # llamada concreta usaba ese None -- confirmado en vivo
                # colgando /api/now-playing mas de 60s sin ninguna
                # respuesta ni excepcion. Con muchas peticiones colgadas
                # acumulandose (el sondeo de "ahora suena" cada 2s) puede
                # llegar a dejar el servidor sin hilos libres, afectando
                # tambien a rutas sin relacion como "salir".
                requests_timeout=10,
            )
        else:
            self._oauth = None

    def _client(self):
        if not self._oauth:
            return None
        if self._rate_limited_until and self._rate_limited_until > time.time():
            # Ya sabemos que Spotify esta devolviendo 429 hasta esta fecha
            # (ver _record_rate_limit) -- seguir intentando peticiones que
            # van a fallar seguro no gana nada y si tiene coste real: por
            # ejemplo kodi_play() llama a spotify.pause() antes de cada
            # reproduccion desde Kodi, y ese round-trip (aunque falle
            # rapido, ~0.5s) se notaba como lentitud al reproducir algo de
            # Kodi mientras Spotify estaba limitado -- confirmado en vivo.
            # Todos los metodos de este gateway pasan por _client(), asi
            # que cortar aqui basta para librarlos a todos de golpe.
            return None
        try:
            # get_cached_token() no solo lee el cache: si el access token ha
            # caducado, intenta refrescarlo contra la API de Spotify ahi
            # mismo, y eso puede lanzar (red caida, refresh_token revocado,
            # scope del cache desactualizado tras cambiar SPOTIFY_SCOPE...).
            # Sin este try/except, cualquier fallo de refresco se propagaba
            # sin capturar hasta la ruta Flask -- un 500 silencioso que en el
            # frontend simplemente parecia "no ha pasado nada" (fetch no
            # lanza en respuestas 4xx/5xx), incluido al intentar reproducir.
            token_info = self._oauth.get_cached_token()
        except Exception:
            return None
        if not token_info:
            return None
        # requests_timeout explicito (aunque 5s ya sea el valor por
        # defecto de spotipy) para que quede claro que es intencional --
        # ver el comentario de requests_timeout en configure(), donde ese
        # mismo valor por defecto SI era None y causaba cuelgues reales.
        #
        # retries=0/status_retries=0 -- el verdadero cuelgue de
        # /api/now-playing (confirmado en vivo, mas de 60s sin respuesta
        # ni excepcion) no era de red: era un 429 "QUOTA_EXCEEDED" de
        # Spotify (limite de peticiones de ESTA app, no una caida general
        # del servicio) con cabecera Retry-After de 53356s (~14.8h).
        # Spotipy, con sus reintentos por defecto (retries=3), usa la
        # libreria urllib3 por debajo, que ante un 429 con Retry-After
        # respeta ese valor literal como tiempo de espera ANTES de cada
        # reintento -- así que se quedaba dormido casi 15h por dentro,
        # sin que requests_timeout (que solo limita cada intento
        # individual, no la espera entre reintentos) pudiera evitarlo.
        # Sin reintentos automaticos, un 429 (o cualquier otro fallo)
        # lanza SpotifyException al momento, que ya se captura mas abajo
        # en cada metodo -- el proximo sondeo (2s despues) ya reintenta
        # solo a nivel de aplicacion.
        # status_forcelist explicito SIN el 429 (los otros son los que trae
        # spotipy por defecto): con retries=0, cualquier status del
        # forcelist se resuelve por dentro como RetryError (sin cabeceras
        # de la respuesta accesibles); dejando el 429 fuera del forcelist,
        # se resuelve como HTTPError normal y SpotifyException SI lleva la
        # cabecera Retry-After en headers (ver _record_rate_limit) --
        # confirmado en vivo comparando ambos casos.
        return spotipy.Spotify(
            auth=token_info["access_token"],
            requests_timeout=10,
            retries=0,
            status_retries=0,
            status_forcelist=(500, 502, 503, 504),
        )

    def _record_rate_limit(self, exc: Exception) -> None:
        """Si exc es un 429 de Spotify con cabecera Retry-After, recuerda
        hasta cuando hay que esperar (ver rate_limited_until) -- para poder
        avisar en el frontend en vez de solo fallar en silencio."""
        if not (SPOTIPY_AVAILABLE and isinstance(exc, spotipy.SpotifyException)):
            return
        if exc.http_status != 429:
            return
        try:
            retry_after = int(exc.headers.get("Retry-After", 0))
        except (TypeError, ValueError, AttributeError):
            retry_after = 0
        if retry_after > 0:
            self._rate_limited_until = time.time() + retry_after

    def rate_limited_until(self) -> float | None:
        """Epoch en segundos hasta el que Spotify pidio esperar (ver
        _record_rate_limit), o None si no hay ningun limite activo conocido
        ahora mismo -- para mostrar un aviso en el frontend."""
        if self._rate_limited_until and self._rate_limited_until > time.time():
            return self._rate_limited_until
        return None

    def seek(self, percentage: float) -> None:
        if self._smtc and self._smtc.seek(percentage):
            return
        sp = self._client()
        if not sp:
            return
        try:
            current = sp.current_playback()
            if not current or not current.get("item"):
                return
            duration_ms = current["item"].get("duration_ms") or 0
            sp.seek_track(int(duration_ms * percentage / 100))
        except Exception:
            pass

    def get_playlist(self) -> list[dict]:
        sp = self._client()
        if not sp:
            return []
        try:
            data = sp.queue()
        except Exception:
            return []
        if not data:
            return []
        playlist = []
        current = data.get("currently_playing")
        if current:
            playlist.append({
                "title": current.get("name", ""),
                "artist": ", ".join(a["name"] for a in current.get("artists", [])),
                "uri": current.get("uri", ""),
                "current": True,
            })
        for item in data.get("queue", []):
            playlist.append({
                "title": item.get("name", ""),
                "artist": ", ".join(a["name"] for a in item.get("artists", [])),
                "uri": item.get("uri", ""),
                "current": False,
            })
        return playlist

    def is_configured(self) -> bool:
        return self._client() is not None

    def get_state(self) -> PlaybackState | None:
        # SMTC primero (ver WindowsSMTCGateway) -- local, sin limite de
        # peticiones, y esto es justo lo que se sondea cada 2s. Si no hay
        # sesion local de Spotify (reproduciendo desde el movil por
        # Connect, o en macOS en desarrollo), cae a la Web API de siempre.
        if self._smtc:
            state = self._smtc.get_state()
            if state:
                return state
        sp = self._client()
        if not sp:
            return None
        try:
            current = sp.current_playback()
        except Exception as e:
            # Sondeado cada 2s (ver NowPlayingService) -- el sitio con mas
            # probabilidad de toparse primero con un 429 de verdad, asi que
            # es donde mas merece la pena registrarlo (ver rate_limited_until).
            self._record_rate_limit(e)
            return None
        if not current or not current.get("item"):
            return None
        item = current["item"]
        images = item.get("album", {}).get("images", [])
        duration = item.get("duration_ms") or 1
        return PlaybackState(
            source="spotify",
            playing=current.get("is_playing", False),
            title=item.get("name", ""),
            artist=", ".join(a["name"] for a in item.get("artists", [])),
            album=item.get("album", {}).get("name", ""),
            art=images[0]["url"] if images else None,
            track_id=item.get("id"),
            progress=int(100 * current.get("progress_ms", 0) / duration),
            elapsed_seconds=current.get("progress_ms", 0) // 1000,
            total_seconds=duration // 1000,
            shuffle=bool(current.get("shuffle_state")),
            repeat=self._REPEAT_FROM_SPOTIFY.get(current.get("repeat_state"), "off"),
        )

    def smtc_art(self) -> tuple[bytes, str] | None:
        """Bytes+mimetype de la caratula leida via SMTC para la cancion
        actual (ver WindowsSMTCGateway.get_art), para la ruta
        /api/library/spotify/smtc-art -- None si no hay SMTC disponible o
        aun no se ha leido ninguna caratula."""
        return self._smtc.get_art() if self._smtc else None

    def control(self, action: str) -> None:
        if self._smtc and self._smtc.control(action):
            return
        sp = self._client()
        if not sp:
            return
        try:
            if action == "playpause":
                playback = sp.current_playback()
                if playback and playback.get("is_playing"):
                    sp.pause_playback()
                else:
                    sp.start_playback()
            elif action == "next":
                sp.next_track()
            elif action == "previous":
                sp.previous_track()
            elif action == "shuffle_toggle":
                playback = sp.current_playback()
                shuffled = bool(playback.get("shuffle_state")) if playback else False
                sp.shuffle(not shuffled)
            elif action == "repeat_cycle":
                playback = sp.current_playback()
                current_repeat = (playback or {}).get("repeat_state", "off")
                sp.repeat(self._REPEAT_CYCLE.get(current_repeat, "off"))
        except Exception as e:
            # Registrar el 429 aqui tambien (no solo en get_state) --
            # confirmado en vivo que si Kodi es la fuente activa,
            # NowPlayingService ni siquiera llega a llamar a
            # spotify.get_state() (Kodi tiene prioridad, ver
            # NowPlayingService.get_state), asi que un rate limit podia
            # quedar sin detectar y cada control de transporte seguia
            # golpeando la Web API en balde.
            self._record_rate_limit(e)

    def pause(self) -> None:
        if self._smtc and self._smtc.pause():
            return
        sp = self._client()
        if not sp:
            return
        try:
            sp.pause_playback()
        except Exception as e:
            # kodi_play() llama a esto antes de CADA reproduccion desde
            # Kodi -- sin registrar el rate limit aqui tambien, cada
            # click en Kodi mientras Kodi es la fuente activa (Spotify.
            # get_state() nunca llega a ejecutarse entonces, ver
            # NowPlayingService) volvia a golpear la Web API en balde, un
            # ~0.5s de mas por cada reproduccion -- justo lo que se
            # notaba como "navegacion por Kodi lenta" incluso con el
            # corte en _client() ya puesto (ese corte no sirve de nada si
            # el limite nunca se llega a registrar).
            self._record_rate_limit(e)

    # ---------- biblioteca / auth ----------

    def _get_all_playlists(self, sp) -> list[dict]:
        """Trae TODAS las playlists del usuario, paginando -- a diferencia
        de un solo current_user_playlists() suelto (que sin parametros
        solo trae la primera pagina, 20 por defecto en la propia API de
        Spotify), esto sigue el "next" hasta agotarlo. Confirmado en vivo
        que sin paginar, tanto el listado de Playlists de la biblioteca
        como la busqueda de Descubrimiento Semanal (ver
        _get_weekly_playlist_id) podian dejar fuera playlists reales --
        incluida Descubrimiento Semanal ya seguida de verdad -- por
        estar mas alla de esa primera pagina."""
        items: list[dict] = []
        try:
            results = sp.current_user_playlists(limit=50)
            while results:
                items.extend(results.get("items", []))
                results = sp.next(results) if results.get("next") else None
        except Exception:
            pass
        return items

    def get_playlists(self) -> list:
        sp = self._client()
        if not sp:
            return []
        items = self._get_all_playlists(sp)
        for item in items:
            images = item.get("images") or []
            item["thumbnail"] = images[0]["url"] if images else None
        return items

    def get_followed_artists(self) -> list[dict]:
        sp = self._client()
        if not sp:
            return []
        try:
            res = sp.current_user_followed_artists(limit=50)
        except Exception:
            return []
        items = (res.get("artists") or {}).get("items", []) if res else []
        return [
            {
                "id": a.get("id"),
                "name": a.get("name", ""),
                "thumbnail": a["images"][0]["url"] if a.get("images") else None,
            }
            for a in items
        ]

    def get_artist_albums(self, artist_id: str) -> list[dict]:
        sp = self._client()
        if not sp:
            return []
        # NO se usa sp.artist_albums() (el metodo de alto nivel de spotipy):
        # confirmado en vivo que el parametro limit que envia siempre --
        # incluso con valores validos (5, 20, 50...) -- hace que Spotify
        # responda 400 "Invalid limit" para este endpoint en concreto. Sin
        # limit funciona bien (Spotify usa 5 por pagina por defecto), asi
        # que se llama al helper HTTP interno de spotipy directamente y se
        # pagina a mano con sp.next() para traer mas de una pagina.
        items: list[dict] = []
        try:
            res = sp._get(f"artists/{artist_id}/albums", include_groups="album,single")
            while res:
                items.extend(res.get("items") or [])
                if len(items) >= 40 or not res.get("next"):
                    break
                res = sp.next(res)
        except Exception:
            pass
        # Spotify repite el mismo album varias veces si esta disponible en
        # distintos mercados -- se queda con la primera aparicion de cada
        # nombre.
        seen: set[str] = set()
        albums = []
        for a in items:
            name = a.get("name", "")
            if name in seen:
                continue
            seen.add(name)
            albums.append({
                "id": a.get("id"),
                "name": name,
                "thumbnail": a["images"][0]["url"] if a.get("images") else None,
                "uri": a.get("uri", ""),
                "year": (a.get("release_date") or "")[:4],
            })
        return albums

    def get_saved_albums(self) -> list[dict]:
        sp = self._client()
        if not sp:
            return []
        try:
            res = sp.current_user_saved_albums(limit=50)
        except Exception:
            return []
        items = res.get("items", []) if res else []
        albums = []
        for entry in items:
            album = entry.get("album") or {}
            albums.append({
                "id": album.get("id"),
                "name": album.get("name", ""),
                "thumbnail": album["images"][0]["url"] if album.get("images") else None,
                "uri": album.get("uri", ""),
                "year": (album.get("release_date") or "")[:4],
            })
        return albums

    def get_album_tracks(self, album_id: str) -> list[dict]:
        sp = self._client()
        if not sp:
            return []
        try:
            res = sp.album_tracks(album_id, limit=50)
        except Exception:
            return []
        items = res.get("items", []) if res else []
        return [
            {
                "title": t.get("name", ""),
                "artist": ", ".join(a["name"] for a in t.get("artists", [])),
                "uri": t.get("uri", ""),
                "duration": (t.get("duration_ms") or 0) // 1000,
            }
            for t in items
        ]

    def get_playlist_tracks(self, playlist_id: str) -> list[dict]:
        sp = self._client()
        if not sp:
            return []
        try:
            res = sp.playlist_items(playlist_id, additional_types=["track"])
        except Exception:
            return []
        tracks = []
        for entry in res.get("items", []):
            track = entry.get("track")
            if not track:
                continue
            tracks.append({
                "title": track.get("name", ""),
                "artist": ", ".join(a["name"] for a in track.get("artists", [])),
                "uri": track.get("uri", ""),
                "duration": (track.get("duration_ms") or 0) // 1000,
            })
        return tracks

    def play_context(self, context_uri: str | None) -> bool:
        if not self._oauth or not context_uri:
            return False
        sp = self._client()
        if not sp:
            return False
        return self._start_playback_with_fallback(sp, context_uri=context_uri)

    def play_track(self, uri: str | None) -> bool:
        if not self._oauth or not uri:
            return False
        sp = self._client()
        if not sp:
            return False
        return self._start_playback_with_fallback(sp, uris=[uri])

    @staticmethod
    def _start_playback_with_fallback(sp, **kwargs) -> bool:
        """Intenta reproducir sin indicar dispositivo (lo normal); si falla,
        reintenta apuntando explicitamente al dispositivo Spotify Connect
        si hay exactamente uno registrado.

        Confirmado en vivo: Spotify puede tener un dispositivo registrado
        (el propio PC, el movil...) sin marcarlo como "activo" tras un
        rato sin usarlo -- start_playback() sin device_id falla entonces
        con "No active device" aunque el dispositivo siga ahi y funcione
        perfectamente si se le indica su ID explicito. Solo se reintenta
        con EXACTAMENTE un dispositivo listado: con varios no hay forma
        fiable de adivinar cual quiere el usuario, mejor el error de
        siempre (pedirle que abra Spotify en el dispositivo que quiera
        usar) que reproducir donde no tocaba."""
        try:
            sp.start_playback(**kwargs)
            return True
        except Exception:
            pass
        try:
            devices = (sp.devices() or {}).get("devices") or []
        except Exception:
            return False
        if len(devices) != 1:
            return False
        try:
            sp.start_playback(device_id=devices[0]["id"], **kwargs)
            return True
        except Exception:
            return False

    # ---------- Fotos de artista (fallback cuando Kodi no tiene) ----------

    def find_artist_image(self, name: str) -> str | None:
        """Busca la foto de un artista por nombre en Spotify, para cuando
        Kodi no tiene ninguna propia (ni siquiera la caratula de su primer
        album como sustituto, ver KodiGateway.get_artists). Cover Art
        Archive no sirve aqui -- solo tiene caratulas de discos, no fotos
        de artista -- asi que se reutiliza Spotify (ya autorizado)."""
        sp = self._client()
        if not sp or not name:
            return None
        key = name.strip().lower()
        if key in self._artist_image_cache:
            return self._artist_image_cache[key]
        artist = self._search_artist(sp, name)
        images = (artist or {}).get("images") or []
        image = images[0]["url"] if images else None
        self._artist_image_cache[key] = image
        return image

    def find_artist(self, name: str) -> dict | None:
        """Busca un artista de Spotify por nombre -- para la vista de
        artista mezclada Kodi+Spotify (ver LibraryService.artist_catalog),
        que necesita el id de Spotify para pedir sus albumes/top tracks."""
        sp = self._client()
        if not sp or not name:
            return None
        return self._search_artist(sp, name)

    @staticmethod
    def _search_artist(sp, name: str) -> dict | None:
        # limit=5, no 1: confirmado en vivo que la busqueda de Spotify puede
        # devolver un top-result DISTINTO (y equivocado) segun el limit
        # pedido para la misma query -- p. ej. "Erasure" con limit=1 daba
        # "Depeche Mode" como unico resultado, con limit=5 el propio Erasure
        # aparecia el primero. Se pide un puñado y, si hay una coincidencia
        # exacta de nombre (sin distinguir mayusculas) entre ellos, se usa
        # esa en vez de fiarse a ciegas del primer resultado.
        try:
            res = sp.search(q=name, type="artist", limit=5)
        except Exception:
            return None
        items = ((res or {}).get("artists") or {}).get("items") or []
        if not items:
            return None
        for item in items:
            if item.get("name", "").strip().lower() == name.strip().lower():
                return item
        return items[0]

    def get_artist_top_tracks(self, artist_id: str) -> list[dict]:
        sp = self._client()
        if not sp or not artist_id:
            return []
        try:
            res = sp.artist_top_tracks(artist_id, country="from_token")
        except Exception:
            return []
        tracks = (res or {}).get("tracks") or []
        return [
            {
                "title": t.get("name", ""),
                "album": (t.get("album") or {}).get("name", ""),
                "uri": t.get("uri", ""),
                "duration": (t.get("duration_ms") or 0) // 1000,
            }
            for t in tracks
        ]

    # ---------- "Me gusta" / Descubrimiento semanal ----------
    #
    # NO se usa GET /me/tracks/contains ni PUT /me/tracks (anadir): ambos
    # devuelven 403 Forbidden, confirmado en vivo con una sesion real y
    # autorizada (mismo token, con el scope user-library-modify concedido).
    # Es una restriccion de la propia API de Spotify (no un bug nuestro):
    # desde sus cambios de noviembre de 2024, esas dos operaciones puntuales
    # de "Your Library" quedan limitadas a apps aprobadas para Extended
    # Quota Mode -- y desde mayo de 2025 Spotify solo aprueba esa extension
    # a organizaciones con 250k+ usuarios activos, no viable para un
    # proyecto personal (ver TODO.md). Por eso no hay boton de "anadir":
    # no hay forma de que funcione via API tal y como esta la cosa.
    #
    # GET /me/tracks (listar toda la biblioteca, sin filtrar por pista) SI
    # funciona sin restriccion, asi que el indicador se resuelve trayendo
    # la lista completa una vez y comparando en local, en vez de preguntar
    # pista a pista.
    LIKED_TRACKS_CACHE_SECONDS = 600

    def _get_liked_track_ids(self, sp) -> set:
        now = time.monotonic()
        if self._liked_track_ids is not None and (now - self._liked_track_ids_fetched_at) < self.LIKED_TRACKS_CACHE_SECONDS:
            return self._liked_track_ids
        ids: set = set()
        try:
            results = sp.current_user_saved_tracks(limit=50)
            while results:
                for item in results.get("items", []):
                    track = item.get("track") or {}
                    if track.get("id"):
                        ids.add(track["id"])
                results = sp.next(results) if results.get("next") else None
        except Exception:
            # Si falla a mitad de la paginacion, mejor quedarse con la
            # cache anterior (si la hay) que con una lista a medias que
            # marcaria canciones reales como "no en Me gusta" por error.
            if self._liked_track_ids is not None:
                return self._liked_track_ids
        self._liked_track_ids = ids
        self._liked_track_ids_fetched_at = now
        return ids

    def get_saved_tracks(self) -> list[dict]:
        """Lista completa de "Me gusta" (GET /me/tracks, paginado) --
        distinto de _get_liked_track_ids (que solo guarda los IDs para el
        indicador ❤️, cacheados 10 min): aqui se trae la info completa de
        cada pista para poder navegarla/reproducirla como una lista mas
        de la biblioteca. Sin cachear -- se pide solo al abrir esta
        pestaña, no en cada sondeo."""
        sp = self._client()
        if not sp:
            return []
        tracks = []
        try:
            results = sp.current_user_saved_tracks(limit=50)
            while results:
                for item in results.get("items", []):
                    track = item.get("track") or {}
                    if not track.get("uri"):
                        continue
                    tracks.append({
                        "title": track.get("name", ""),
                        "artist": ", ".join(a["name"] for a in track.get("artists", [])),
                        "uri": track.get("uri", ""),
                        "duration": (track.get("duration_ms") or 0) // 1000,
                    })
                results = sp.next(results) if results.get("next") else None
        except Exception:
            pass
        return tracks

    def play_saved_tracks(self) -> bool:
        """"Reproducir todo" para Me gusta -- a diferencia de una
        playlist normal, Me gusta no tiene un context_uri que se le
        pueda pasar a start_playback (no es una playlist real, es la
        coleccion "Your Library" del usuario), asi que se le pasa la
        lista de URIs directamente. Tope de 200 pistas: start_playback
        acepta una lista de uris pero no esta pensado para colecciones
        enormes -- con "Me gusta" pudiendo tener miles de canciones,
        pedirlas todas de golpe seria lento y probablemente rechazado
        por la propia API: 200 ya cubre de sobra un "reproducir ahora y
        que seguir sonando" razonable."""
        sp = self._client()
        if not sp:
            return False
        uris = []
        try:
            results = sp.current_user_saved_tracks(limit=50)
            while results and len(uris) < 200:
                for item in results.get("items", []):
                    track = item.get("track") or {}
                    if track.get("uri"):
                        uris.append(track["uri"])
                    if len(uris) >= 200:
                        break
                results = sp.next(results) if results.get("next") else None
        except Exception:
            return False
        if not uris:
            return False
        return self._start_playback_with_fallback(sp, uris=uris)

    def is_track_liked(self, track_id: str) -> bool:
        sp = self._client()
        if not sp or not track_id:
            return False
        return track_id in self._get_liked_track_ids(sp)

    def _get_weekly_playlist_id(self, sp) -> str | None:
        if self._weekly_playlist_id:
            return self._weekly_playlist_id
        for p in self._get_all_playlists(sp):
            if (p.get("name") or "").strip().lower() in WEEKLY_PLAYLIST_NAMES:
                self._weekly_playlist_id = p.get("id")
                break
        return self._weekly_playlist_id

    def is_track_in_weekly(self, track_id: str) -> bool:
        """True si la pista esta en el "Descubrimiento semanal"/"Discover
        Weekly" del usuario. Solo lectura -- la API de Spotify no deja
        añadir canciones a esta playlist (la genera el algoritmo, no
        pertenece al usuario; un intento de Playlist.Add ahi da 403)."""
        sp = self._client()
        if not sp or not track_id:
            return False
        playlist_id = self._get_weekly_playlist_id(sp)
        if not playlist_id:
            return False
        try:
            res = sp.playlist_items(playlist_id, fields="items.track.id")
            ids = {it.get("track", {}).get("id") for it in res.get("items", []) if it.get("track")}
        except Exception:
            return False
        return track_id in ids

    def get_authorize_url(self) -> str | None:
        return self._oauth.get_authorize_url() if self._oauth else None

    def exchange_code(self, code: str | None) -> bool:
        if not self._oauth or not code:
            return False
        try:
            # Puede lanzar (codigo ya usado o caducado -- Spotify los emite
            # de un solo uso y expiran a los pocos minutos -- credenciales
            # cambiadas entre /login y /callback, red caida...). Sin este
            # try/except se propagaba sin capturar hasta la ruta Flask,
            # dando un 500 "Internal Server Error" crudo en vez de la
            # pagina de error normal ("No se pudo autorizar") -- confirmado
            # en vivo visitando /callback con un codigo ya no valido.
            self._oauth.get_access_token(code, as_dict=False)
        except Exception:
            return False
        return True
