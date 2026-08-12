from urllib.parse import quote

import requests

from ambar.domain.playback import PlaybackState


class KodiGateway:
    """Adapter hacia Kodi: JSON-RPC por HTTP, mas la URL de WebSocket para eventos."""

    def __init__(self, host: str, port: str, cd_identifier=None):
        self.host = host
        self.port = port
        self._cd_identifier = cd_identifier

    @property
    def rpc_url(self) -> str:
        return f"http://{self.host}:{self.port}/jsonrpc"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:9090/jsonrpc"

    def rpc(self, method: str, params: dict | None = None):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params:
            payload["params"] = params
        try:
            r = requests.post(self.rpc_url, json=payload, timeout=2)
            return r.json().get("result")
        except Exception:
            return None

    def get_state(self) -> PlaybackState | None:
        players = self.rpc("Player.GetActivePlayers")
        if not players:
            return None
        player_id = players[0]["playerid"]
        item = self.rpc("Player.GetItem", {
            "playerid": player_id,
            "properties": ["title", "artist", "album", "thumbnail", "file"],
        })
        props = self.rpc("Player.GetProperties", {
            "playerid": player_id,
            "properties": ["percentage", "speed", "time", "totaltime"],
        })
        if not item or "item" not in item:
            return None
        info = item["item"]
        art = None
        thumb = info.get("thumbnail")
        if thumb:
            art = "/api/art?path=" + quote(thumb, safe="")
        title = info.get("title") or info.get("label") or "Pista sin titulo"
        artist = ", ".join(info.get("artist", [])) or "CD / biblioteca local"
        album = info.get("album", "")
        title, artist, album, art = self._enrich_cd_now_playing(
            info.get("file", ""), title, artist, album, art
        )
        return PlaybackState(
            source="kodi",
            playing=bool(props and props.get("speed", 0) != 0),
            title=title,
            artist=artist,
            album=album,
            art=art,
            progress=(props or {}).get("percentage", 0),
            elapsed_seconds=self._time_to_seconds((props or {}).get("time")),
            total_seconds=self._time_to_seconds((props or {}).get("totaltime")),
        )

    def _enrich_cd_now_playing(self, file_path: str, title: str, artist: str, album: str, art: str | None):
        """Sustituye titulo/artista/album/caratula genericos de Kodi para
        una pista de CD por los datos reales de MusicBrainz, si ya se
        identifico el disco (ver get_audio_cd_metadata). Solo usa lo que
        ya este en cache -- get_last() no hace ninguna llamada de red ni a
        Kodi, para no bloquear el sondeo de "ahora suena" (cada 2s).

        Si el disco aun no se ha identificado (p. ej. el CD se puso a
        reproducir desde el propio Kodi sin pasar antes por la pestaña CD
        de Ambar, o la identificacion anterior fallo por una conexion
        lenta), se queda con lo generico de Kodi para ESTE sondeo, pero
        lanza una identificacion de fondo (identify_async, no bloqueante)
        para que se autorrecupere sola en un sondeo siguiente -- sin
        necesidad de que alguien pulse el boton de actualizar a mano."""
        if not file_path.startswith("cdda://") or not self._cd_identifier:
            return title, artist, album, art
        cd_meta = self._cd_identifier.get_last()
        if not cd_meta:
            toc = self.get_audio_cd_toc()
            if toc:
                self._cd_identifier.identify_async(toc)
            return title, artist, album, art
        title = self._track_title_at(file_path, cd_meta.get("tracks") or []) or title
        return title, cd_meta.get("artist") or artist, cd_meta.get("title") or album, cd_meta.get("art") or art

    @staticmethod
    def _time_to_seconds(time_obj: dict | None) -> int:
        if not time_obj:
            return 0
        return time_obj.get("hours", 0) * 3600 + time_obj.get("minutes", 0) * 60 + time_obj.get("seconds", 0)

    def control(self, action: str) -> None:
        players = self.rpc("Player.GetActivePlayers")
        if not players:
            return
        pid = players[0]["playerid"]
        if action == "playpause":
            self.rpc("Player.PlayPause", {"playerid": pid})
        elif action == "next":
            self.rpc("Player.GoTo", {"playerid": pid, "to": "next"})
        elif action == "previous":
            self.rpc("Player.GoTo", {"playerid": pid, "to": "previous"})

    def stop(self) -> None:
        players = self.rpc("Player.GetActivePlayers")
        if not players:
            return
        self.rpc("Player.Stop", {"playerid": players[0]["playerid"]})

    def pause(self) -> None:
        # "play": False fuerza pausa explicita -- a diferencia de
        # control("playpause"), que alterna (Player.PlayPause sin ese
        # parametro), esto no arriesga a REANUDAR a Kodi si ya estaba en
        # pausa. Usado por NowPlayingService para parar Kodi cuando
        # Spotify empieza a sonar (ver enforce_single_source).
        players = self.rpc("Player.GetActivePlayers")
        if not players:
            return
        self.rpc("Player.PlayPause", {"playerid": players[0]["playerid"], "play": False})

    # ---------- biblioteca ----------

    def get_artists(self) -> list:
        res = self.rpc("AudioLibrary.GetArtists", {"properties": ["thumbnail"]})
        artists = res.get("artists", []) if res else []
        # Muchas bibliotecas de Kodi no tienen imagen de artista scrapeada
        # (thumbnail: "" para todos, confirmado en vivo) aunque sí tengan
        # caratula de album. En vez de dejar el hueco vacio, se usa la
        # caratula del primer album de cada artista como sustituto -- una
        # sola llamada extra a AudioLibrary.GetAlbums (todos los albumes de
        # golpe), no una por artista.
        missing = [a for a in artists if not a.get("thumbnail")]
        if missing:
            albums_res = self.rpc("AudioLibrary.GetAlbums", {"properties": ["thumbnail", "artist"]})
            albums = albums_res.get("albums", []) if albums_res else []
            thumb_by_artist: dict[str, str] = {}
            for album in albums:
                thumb = album.get("thumbnail")
                if not thumb:
                    continue
                for artist_name in album.get("artist", []):
                    thumb_by_artist.setdefault(artist_name, thumb)
            for artist in missing:
                fallback = thumb_by_artist.get(artist.get("artist"))
                if fallback:
                    artist["thumbnail"] = fallback
        return artists

    def get_albums(self, artist_id: int | None = None) -> list:
        # Ya no busca caratula externa aqui -- consultar MusicBrainz por
        # cada album sin caratula propia antes de devolver la respuesta
        # hacia tardar mucho en aparecer el listado (mismo problema que
        # tenia kodi_artists(), ver find_album_art). El frontend pinta el
        # listado al instante con lo que ya tiene Kodi y pide la caratula
        # de cada album sin ella aparte, en paralelo con spinner.
        params = {"properties": ["thumbnail", "year", "artist"]}
        if artist_id is not None:
            params["filter"] = {"artistid": artist_id}
        res = self.rpc("AudioLibrary.GetAlbums", params)
        return res.get("albums", []) if res else []

    def find_album_art(self, artist: str, title: str) -> str | None:
        if not self._cd_identifier or not artist or not title:
            return None
        return self._cd_identifier.find_album_art(artist, title)

    def get_songs(self, album_id: int | None = None) -> list:
        params = {"properties": ["duration", "track", "thumbnail"]}
        if album_id is not None:
            params["filter"] = {"albumid": album_id}
        res = self.rpc("AudioLibrary.GetSongs", params)
        return res.get("songs", []) if res else []

    def find_artist_by_name(self, name: str) -> dict | None:
        """Busca un artista de la biblioteca de Kodi por nombre exacto --
        para la vista de artista (ver LibraryService.artist_catalog), que
        parte del nombre tal cual aparece en "ahora suena", no de un id."""
        res = self.rpc("AudioLibrary.GetArtists", {
            "properties": ["thumbnail"],
            "filter": {"field": "artist", "operator": "is", "value": name},
        })
        artists = (res or {}).get("artists") or []
        return artists[0] if artists else None

    def get_artist_songs(self, artist_id: int) -> list:
        res = self.rpc("AudioLibrary.GetSongs", {
            "properties": ["duration", "thumbnail", "album"],
            "filter": {"artistid": artist_id},
        })
        return (res or {}).get("songs") or []

    def get_directory(self, path: str = "sources://music/") -> list:
        if path == "sources://music/":
            # Files.GetDirectory con directory="sources://music/" devuelve
            # "Invalid params" en esta build de Kodi (probado en vivo con
            # varias combinaciones de properties, incluso sin ninguna) --
            # parece un bug/limitacion de Kodi especifico de "music" como
            # media con la ruta virtual sources:// (con "video" si funciona).
            # Files.GetSources es el equivalente para listar el nivel raiz.
            res = self.rpc("Files.GetSources", {"media": "music"})
            sources = res.get("sources", []) if res else []
            for source in sources:
                source["filetype"] = "directory"
            return sources
        res = self.rpc("Files.GetDirectory", {
            "directory": path,
            "media": "music",
            "properties": ["thumbnail", "file", "mimetype"],
        })
        files = res.get("files", []) if res else []
        if path.startswith("cdda://"):
            self._enrich_cd_track_labels(files)
        return files

    def _enrich_cd_track_labels(self, files: list) -> None:
        """Sustituye las etiquetas genericas "Track NN" de Kodi por los
        titulos reales cuando MusicBrainz identifica el CD (bloqueante:
        esta ruta la dispara el usuario al entrar en la pestaña CD, no un
        sondeo periodico, asi que una consulta de red aqui es aceptable --
        UX ya cubierta por el spinner de carga del frontend). Si no hay
        coincidencia o falla la consulta, deja las etiquetas de Kodi tal
        cual (mismo fallback que el resto de adapters de audio)."""
        metadata = self.get_audio_cd_metadata()
        tracks = (metadata or {}).get("tracks") or []
        for f in files:
            title = self._track_title_at(f.get("file", ""), tracks)
            if title:
                f["label"] = title

    def seek(self, percentage: float) -> None:
        players = self.rpc("Player.GetActivePlayers")
        if not players:
            return
        self.rpc("Player.Seek", {
            "playerid": players[0]["playerid"],
            "value": {"percentage": percentage},
        })

    def get_playlist(self) -> list[dict]:
        players = self.rpc("Player.GetActivePlayers")
        if not players:
            return []
        pid = players[0]["playerid"]
        props = self.rpc("Player.GetProperties", {"playerid": pid, "properties": ["position"]})
        current_position = (props or {}).get("position", -1)
        res = self.rpc("Playlist.GetItems", {
            "playlistid": 0,
            "properties": ["title", "artist", "album", "file"],
        })
        items = res.get("items", []) if res else []
        # Los titulos de CD que da Kodi son genericos ("Track 01"...); si
        # hay alguna pista de CD en la lista, se identifica una sola vez
        # (no por pista) y se usa para sustituir titulo/artista reales,
        # igual que en el listado de la pestaña CD y en "ahora suena".
        cd_metadata = None
        if any(it.get("file", "").startswith("cdda://") for it in items):
            cd_metadata = self.get_audio_cd_metadata()
        cd_tracks = (cd_metadata or {}).get("tracks") or []
        result = []
        for idx, it in enumerate(items):
            title = it.get("title") or it.get("label") or "Pista sin titulo"
            artist = ", ".join(it.get("artist", []))
            cd_title = self._track_title_at(it.get("file", ""), cd_tracks)
            if cd_title:
                title = cd_title
                artist = cd_metadata.get("artist") or artist
            result.append({
                "position": idx,
                "title": title,
                "artist": artist,
                "current": idx == current_position,
            })
        return result

    def goto_position(self, position: int) -> None:
        players = self.rpc("Player.GetActivePlayers")
        if not players:
            return
        self.rpc("Player.GoTo", {"playerid": players[0]["playerid"], "to": position})

    def is_reachable(self) -> bool:
        return self.rpc("JSONRPC.Ping") == "pong"

    def has_audio_cd(self) -> bool:
        """True si Kodi puede listar pistas reales en cdda://local/ (CD de
        audio Redbook/CDDA insertado y legible) -- no confundir con un
        disco de datos con FLAC/MP3 (esos se navegan como una fuente de
        archivos normal, no por aqui).

        NO usa XBMC.GetInfoBooleans (system.hasmediadvdaudio/
        system.hasaudiocd): confirmado en vivo en Windows que ambos
        booleanos se quedan en False de forma permanente incluso con un CD
        de audio insertado y reproducible sin problema por Kodi (via la
        fuente "G: (Audio-CD)" que Kodi crea solo) -- solo
        system.hasmediadvd (generico, cualquier disco optico) daba True.
        Probar cdda://local/ directamente es lo unico que reflejo el
        estado real: hay que fiarse del propio recurso que usa la pestaña
        CD, no de los booleanos de estado de Kodi."""
        return bool(self.get_audio_cd_toc())

    def get_audio_cd_toc(self) -> list[int] | None:
        """Tabla de contenidos (TOC) del CD insertado, en el formato que
        espera la busqueda por TOC de MusicBrainz: [pista_inicial,
        pista_final, offset_leadout, offset_pista_1, ..., offset_pista_N],
        todo en sectores/frames CD-DA (75 por segundo). Kodi no expone
        esto directamente via JSON-RPC, asi que se deriva del tamaño en
        bytes de cada pista de cdda://local/ (2352 bytes = 1 sector CD-DA
        de audio, 176400 bytes/s = 44100Hz * 2 canales * 2 bytes; probado
        en vivo que los tamaños que da Kodi son multiplos exactos de
        2352). None si no hay CD insertado/legible."""
        res = self.rpc("Files.GetDirectory", {
            "directory": "cdda://local/", "media": "music", "properties": ["size"],
        })
        files = (res or {}).get("files") or []
        if not files:
            return None
        FRAME_BYTES = 2352
        offset = 150  # pregap estandar de 2s (00:02:00 en MSF)
        track_offsets = []
        for f in files:
            track_offsets.append(offset)
            offset += f.get("size", 0) // FRAME_BYTES
        return [1, len(files), offset] + track_offsets

    def get_audio_cd_metadata(self, force: bool = False) -> dict | None:
        """Identifica el CD insertado contra MusicBrainz (titulo, artista,
        pistas, caratula) -- None si no hay identificador configurado, no
        hay CD, o no se encontro coincidencia. force=True ignora la cache
        (boton "actualizar" del CD tab)."""
        if not self._cd_identifier:
            return None
        toc = self.get_audio_cd_toc()
        if not toc:
            return None
        return self._cd_identifier.identify(toc, force=force)

    @staticmethod
    def _track_title_at(file_path: str, tracks: list[str]) -> str | None:
        """Titulo real (MusicBrainz) para una pista cdda://local/NN.cdda,
        dada la lista de pistas ya identificada -- None si no aplica o la
        posicion no tiene titulo. Comparte la logica de "posicion de
        fichero -> indice de la lista de pistas" entre el listado de la
        pestaña CD y la lista de reproduccion, sin repetir la consulta de
        identificacion por cada pista."""
        if not file_path.startswith("cdda://") or not tracks:
            return None
        try:
            position = int(file_path.rsplit("/", 1)[-1].split(".")[0])
        except (ValueError, IndexError):
            return None
        if 1 <= position <= len(tracks) and tracks[position - 1]:
            return tracks[position - 1]
        return None

    def play(self, item: dict) -> None:
        self.rpc("Playlist.Clear", {"playlistid": 0})
        self.rpc("Playlist.Add", {"playlistid": 0, "item": item})
        self.rpc("Player.Open", {"item": {"playlistid": 0}})

    def art_proxy(self, path: str) -> tuple[bytes | str, int, str | None]:
        # `path` llega aqui ya decodificado una vez por Flask (request.args
        # lo desescapa al parsear la query string). El webserver de Kodi
        # espera la URL image:// completa codificada como un unico segmento
        # de path -- hay que volver a codificarla, si no Kodi ve barras/
        # dos-puntos sueltos y no la resuelve (404).
        img_url = f"http://{self.host}:{self.port}/image/{quote(path, safe='')}"
        try:
            r = requests.get(img_url, timeout=3)
            return r.content, r.status_code, r.headers.get("Content-Type", "image/jpeg")
        except Exception:
            return "", 404, None
