import base64
import sys

from ambar.adapters.deezer.gateway import DeezerGateway
from ambar.adapters.kodi.gateway import KodiGateway
from ambar.adapters.spotify.gateway import SpotifyGateway

# Carátula de "Canciones que te gustan" (fondo azul + corazón rosa, mismo
# estilo que usa la propia Spotify para esta lista) -- no es una imagen
# real de Spotify (esta "playlist" es sintética, ver LIKED_SONGS_ID, sin
# caratula propia que pedirle a la API), asi que se genera un SVG propio
# en vez de anadir un fichero de imagen aparte al repo. Codificado en
# base64 (no URL-encoded) para poder ir directo en un atributo HTML
# `<img src="...">` sin escapar comillas/ángulos: el frontend inserta
# `thumbnail` tal cual en una plantilla de texto (ver renderGridSpotify
# en index.html), no hay ningun escapado de por medio.
_LIKED_SONGS_ART_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0%" stop-color="#4f5cdb"/>'
    '<stop offset="100%" stop-color="#141b4d"/>'
    '</linearGradient></defs>'
    '<rect width="24" height="24" fill="url(#g)"/>'
    '<path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 '
    '7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 '
    '5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" '
    'fill="#ff2f92"/></svg>'
)
LIKED_SONGS_ART = "data:image/svg+xml;base64," + base64.b64encode(
    _LIKED_SONGS_ART_SVG.encode("utf-8")
).decode("ascii")


class LibraryService:
    """Orquesta la navegacion de biblioteca nativa de Kodi y las playlists de Spotify."""

    def __init__(
        self, kodi_gateway: KodiGateway, spotify_gateway: SpotifyGateway, deezer_gateway: DeezerGateway | None = None
    ):
        self._kodi = kodi_gateway
        self._spotify = spotify_gateway
        # Sin credenciales/config propia (API publica sin autenticacion), asi
        # que un valor por defecto es seguro -- opcional solo para no forzar
        # a pasarlo en los dobles de test que no ejercitan kodi_artists().
        self._deezer = deezer_gateway or DeezerGateway()

    def kodi_status(self) -> dict:
        return {"available": self._kodi.is_reachable()}

    def spotify_status(self) -> dict:
        return {
            "available": self._spotify.is_configured(),
            # Epoch (segundos) hasta el que Spotify pidio esperar tras un
            # 429 "rate limit" (ver SpotifyGateway.rate_limited_until), o
            # None si no hay ninguno activo -- para avisar en el frontend
            # en vez de dejar que parezca simplemente roto.
            "rate_limited_until": self._spotify.rate_limited_until(),
        }

    def spotify_smtc_art(self) -> tuple[bytes, str] | None:
        return self._spotify.smtc_art()

    def spotify_track_status(self, track_id: str) -> dict:
        # Estado de la pista actual respecto a "Me gusta" y al Descubrimiento
        # semanal -- ambos de solo lectura (ver SpotifyGateway: anadir a "Me
        # gusta" via API da 403 Forbidden para esta app, restriccion de
        # Spotify no de nuestro codigo, documentado en TODO.md).
        if not track_id:
            return {"liked": False, "in_weekly": False}
        return {
            "liked": self._spotify.is_track_liked(track_id),
            "in_weekly": self._spotify.is_track_in_weekly(track_id),
        }

    def kodi_artists(self) -> list:
        # Ya no busca fotos aqui: hacerlo de forma sincrona (una consulta
        # HTTP a Spotify/Deezer por artista sin foto, antes de devolver la
        # respuesta) es lo que hacia tardar mucho en aparecer el listado
        # completo -- confirmado en vivo. El frontend pinta la lista al
        # instante con lo que ya tiene Kodi y pide la foto de cada artista
        # sin ella aparte (ver artist_image / /api/library/kodi/artist-image),
        # una peticion por artista en paralelo (con spinner mientras tanto).
        return self._kodi.get_artists()

    def artist_image(self, name: str) -> str | None:
        if not name:
            return None
        # Spotify primero (ya autorizado, buena cobertura); si no esta
        # configurado o no encuentra el artista, Deezer de respaldo
        # (publico, sin autenticacion, siempre disponible).
        return self._spotify.find_artist_image(name) or self._deezer.find_artist_image(name)

    def artist_catalog(self, name: str) -> dict:
        """Albumes y canciones de un artista, mezclando Kodi y Spotify --
        para el click en el nombre del artista de "ahora suena" (funciona
        sea cual sea la fuente que esta sonando). Si el mismo album esta en
        las dos fuentes se muestra una sola vez, con ambas disponibles para
        elegir donde reproducirlo (ver _merge_catalog).

        Las canciones son solo de Kodi: el "top tracks" de un artista en
        Spotify (GET /artists/{id}/top-tracks) da 403 Forbidden para esta
        app -- misma restriccion de "Extended Quota Mode" que "Me gusta"
        (ver TODO.md), no arreglable desde aqui. Los albumes de Spotify si
        funcionan sin restriccion."""
        if not name:
            return {"artist": name, "albums": [], "songs": []}

        kodi_albums, kodi_songs = [], []
        kodi_artist = self._kodi.find_artist_by_name(name)
        if kodi_artist:
            kodi_albums = self._kodi.get_albums(kodi_artist["artistid"])
            kodi_songs = self._kodi.get_artist_songs(kodi_artist["artistid"])

        spotify_albums = []
        sp_artist = self._spotify.find_artist(name)
        if sp_artist:
            spotify_albums = self._spotify.get_artist_albums(sp_artist["id"])

        albums = self._merge_catalog(
            [(a.get("label") or a.get("title") or "", a.get("thumbnail") or "", {"albumid": a.get("albumid")}) for a in kodi_albums],
            [(a.get("name") or "", a.get("thumbnail") or "", {"uri": a.get("uri")}) for a in spotify_albums],
        )
        songs = [
            {
                "title": s.get("label") or s.get("title") or "",
                "album": s.get("album", ""),
                "sources": [{"source": "kodi", "songid": s.get("songid")}],
            }
            for s in kodi_songs
        ]
        return {"artist": name, "albums": albums, "songs": songs}

    @staticmethod
    def _merge_catalog(kodi_items: list[tuple], spotify_items: list[tuple]) -> list[dict]:
        """Combina dos listas (titulo, caratula, datos_de_fuente) en una
        sola por titulo (sin distinguir mayusculas): si el mismo titulo
        aparece en las dos, el resultado lleva ambas fuentes en "sources"
        en vez de duplicarse -- el frontend deja elegir cual usar cuando
        hay mas de una."""
        merged: dict[str, dict] = {}
        order: list[str] = []
        tagged = [(t, th, sd, "kodi") for t, th, sd in kodi_items] + [
            (t, th, sd, "spotify") for t, th, sd in spotify_items
        ]
        for title, thumbnail, source_data, source_name in tagged:
            if not title:
                continue
            key = title.strip().lower()
            if key not in merged:
                merged[key] = {"title": title, "thumbnail": thumbnail, "sources": []}
                order.append(key)
            entry = merged[key]
            if not entry["thumbnail"] and thumbnail:
                entry["thumbnail"] = thumbnail
            entry["sources"].append({"source": source_name, **source_data})
        return [merged[k] for k in order]

    def kodi_albums(self, artist_id: int | None) -> list:
        return self._kodi.get_albums(artist_id)

    def album_art(self, artist: str, title: str, force: bool = False) -> str | None:
        return self._kodi.find_album_art(artist, title, force=force)

    def kodi_songs(self, album_id: int | None) -> list:
        return self._kodi.get_songs(album_id)

    def kodi_directory(self, path: str) -> list:
        return self._kodi.get_directory(path)

    def kodi_cd_status(self) -> dict:
        # En macOS, Kodi no detecta de forma fiable los CD de audio
        # (system.hasmediadvdaudio da False incluso con un CD_DA real
        # insertado, confirmado con diskutil -- limitacion conocida de los
        # builds de Kodi para macOS, no de esta app). En Windows/Linux la
        # deteccion nativa de Kodi deberia ser fiable, asi que ahi si se usa
        # para habilitar/deshabilitar la pestaña de verdad.
        return {
            "available": self._kodi.has_audio_cd(),
            "detection_reliable": sys.platform != "darwin",
        }

    def kodi_cd_metadata(self, force: bool = False) -> dict:
        # Identificacion online del CD contra MusicBrainz (titulo, artista,
        # pistas, caratula) -- ver KodiGateway.get_audio_cd_metadata. None
        # si no hay CD, no hay internet, o no se encontro coincidencia (CDs
        # promocionales/no catalogados): "available" queda en False y el
        # frontend sigue mostrando las etiquetas genericas de Kodi. force=True
        # ignora la cache en disco (boton "actualizar" del CD tab).
        metadata = self._kodi.get_audio_cd_metadata(force=force)
        if not metadata:
            return {"available": False}
        return {"available": True, **metadata}

    def kodi_eject_cd(self) -> bool:
        return self._kodi.eject_cd()

    def kodi_play(self, body: dict) -> None:
        self._spotify.pause()
        item = {}
        if "songid" in body:
            item["songid"] = body["songid"]
        elif "albumid" in body:
            item["albumid"] = body["albumid"]
        elif "artistid" in body:
            item["artistid"] = body["artistid"]
        elif "directory" in body:
            # Una carpeta/CD (path VFS) no se reproduce con "file" -- Kodi
            # espera "file" para un fichero individual y da "Invalid params"
            # si se le pasa una carpeta ahi. "directory" es el campo correcto
            # para reproducir el contenido completo de una carpeta (verificado
            # en vivo contra Kodi: Playlist.Add con file=carpeta -> error,
            # con directory=carpeta -> expande todas las pistas).
            item["directory"] = body["directory"]
        elif "file" in body:
            item["file"] = body["file"]
        self._kodi.play(item)

    # ID/context_uri sintetico para "Canciones que te gustan" -- no es una
    # playlist real de Spotify (no tiene id/context_uri propios, "Me
    # gusta" es la coleccion "Your Library" del usuario, otro endpoint
    # por completo, ver SpotifyGateway.get_saved_tracks), pero se la
    # trata como una playlist mas de cara al frontend (mismo flujo de
    # listar/reproducir que cualquier otra) para no duplicar toda la
    # navegacion de dos niveles solo para este caso.
    LIKED_SONGS_ID = "liked"

    def spotify_playlists(self) -> list:
        # "Me gusta" siempre primero (fijado, igual que en la propia app
        # de Spotify), el resto alfabeticamente -- antes se mostraban en
        # el orden que diera la API (el de la barra lateral de Spotify
        # del usuario, no alfabetico ni predecible).
        playlists = sorted(self._spotify.get_playlists(), key=lambda p: (p.get("name") or "").strip().lower())
        liked = {"id": self.LIKED_SONGS_ID, "name": "Canciones que te gustan", "thumbnail": LIKED_SONGS_ART, "uri": self.LIKED_SONGS_ID}
        return [liked] + playlists

    def spotify_playlist_tracks(self, playlist_id: str | None) -> list:
        if playlist_id == self.LIKED_SONGS_ID:
            return self._spotify.get_saved_tracks()
        return self._spotify.get_playlist_tracks(playlist_id) if playlist_id else []

    def spotify_artists(self) -> list:
        return self._spotify.get_followed_artists()

    def spotify_artist_albums(self, artist_id: str | None) -> list:
        return self._spotify.get_artist_albums(artist_id) if artist_id else []

    def spotify_albums(self) -> list:
        return self._spotify.get_saved_albums()

    def spotify_album_tracks(self, album_id: str | None) -> list:
        return self._spotify.get_album_tracks(album_id) if album_id else []

    def spotify_play(self, context_uri: str | None) -> bool:
        self._kodi.stop()
        if context_uri == self.LIKED_SONGS_ID:
            # "Me gusta" no tiene context_uri real que pasarle a
            # start_playback (no es una playlist) -- se le pasan las
            # URIs de las pistas directamente, ver play_saved_tracks.
            return self._spotify.play_saved_tracks()
        return self._spotify.play_context(context_uri)

    def spotify_play_track(self, uri: str | None) -> bool:
        self._kodi.stop()
        return self._spotify.play_track(uri)
