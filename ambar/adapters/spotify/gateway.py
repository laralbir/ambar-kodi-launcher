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

    def __init__(self, cache_path: str):
        self._cache_path = cache_path
        self._oauth: "SpotifyOAuth | None" = None
        # ID de la playlist "Descubrimiento semanal"/"Discover Weekly" del
        # usuario -- estable entre semanas (solo cambia el contenido, no el
        # ID), asi que una vez encontrada se cachea en memoria y no hace
        # falta volver a buscarla por nombre en cada comprobacion.
        self._weekly_playlist_id: str | None = None
        # Cache de IDs de canciones en "Me gusta" (ver _get_liked_track_ids
        # mas abajo, seccion "Me gusta"/Descubrimiento semanal).
        self._liked_track_ids: set | None = None
        self._liked_track_ids_fetched_at: float = 0.0

    def configure(self, client_id: str | None, client_secret: str | None, redirect_uri: str) -> None:
        if SPOTIPY_AVAILABLE and client_id and client_secret:
            self._oauth = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=SPOTIFY_SCOPE,
                cache_path=self._cache_path,
                open_browser=False,
            )
        else:
            self._oauth = None

    def _client(self):
        if not self._oauth:
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
        return spotipy.Spotify(auth=token_info["access_token"])

    def seek(self, percentage: float) -> None:
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
        sp = self._client()
        if not sp:
            return None
        try:
            current = sp.current_playback()
        except Exception:
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
        )

    def control(self, action: str) -> None:
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
        except Exception:
            pass

    def pause(self) -> None:
        sp = self._client()
        if not sp:
            return
        try:
            sp.pause_playback()
        except Exception:
            pass

    # ---------- biblioteca / auth ----------

    def get_playlists(self) -> list:
        sp = self._client()
        if not sp:
            return []
        try:
            res = sp.current_user_playlists()
        except Exception:
            return []
        items = res.get("items", []) if res else []
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
        try:
            res = sp.artist_albums(artist_id, album_type="album,single", limit=50)
        except Exception:
            return []
        items = res.get("items", []) if res else []
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
        try:
            sp.start_playback(context_uri=context_uri)
        except Exception:
            # Antes esto se tragaba y devolvia True igualmente -- el
            # frontend cerraba la biblioteca dando la falsa impresion de que
            # habia empezado a sonar cuando en realidad Spotify rechazo la
            # llamada (caso mas comun: no hay ningun dispositivo Connect
            # activo en ese momento, error "No active device").
            return False
        return True

    def play_track(self, uri: str | None) -> bool:
        if not self._oauth or not uri:
            return False
        sp = self._client()
        if not sp:
            return False
        try:
            sp.start_playback(uris=[uri])
        except Exception:
            return False
        return True

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

    def is_track_liked(self, track_id: str) -> bool:
        sp = self._client()
        if not sp or not track_id:
            return False
        return track_id in self._get_liked_track_ids(sp)

    def _get_weekly_playlist_id(self, sp) -> str | None:
        if self._weekly_playlist_id:
            return self._weekly_playlist_id
        try:
            res = sp.current_user_playlists(limit=50)
            items = res.get("items", []) if res else []
            for p in items:
                if (p.get("name") or "").strip().lower() in WEEKLY_PLAYLIST_NAMES:
                    self._weekly_playlist_id = p.get("id")
                    break
        except Exception:
            pass
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
        self._oauth.get_access_token(code, as_dict=False)
        return True
