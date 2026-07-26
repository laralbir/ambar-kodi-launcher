from urllib.parse import quote

import requests

from ambar.domain.playback import PlaybackState


class KodiGateway:
    """Adapter hacia Kodi: JSON-RPC por HTTP, mas la URL de WebSocket para eventos."""

    def __init__(self, host: str, port: str):
        self.host = host
        self.port = port

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
            "properties": ["title", "artist", "album", "thumbnail"],
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
        return PlaybackState(
            source="kodi",
            playing=bool(props and props.get("speed", 0) != 0),
            title=info.get("title") or info.get("label") or "Pista sin titulo",
            artist=", ".join(info.get("artist", [])) or "CD / biblioteca local",
            album=info.get("album", ""),
            art=art,
            progress=(props or {}).get("percentage", 0),
            elapsed_seconds=self._time_to_seconds((props or {}).get("time")),
            total_seconds=self._time_to_seconds((props or {}).get("totaltime")),
        )

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

    # ---------- biblioteca ----------

    def get_artists(self) -> list:
        res = self.rpc("AudioLibrary.GetArtists", {"properties": ["thumbnail"]})
        return res.get("artists", []) if res else []

    def get_albums(self, artist_id: int | None = None) -> list:
        params = {"properties": ["thumbnail", "year", "artist"]}
        if artist_id is not None:
            params["filter"] = {"artistid": artist_id}
        res = self.rpc("AudioLibrary.GetAlbums", params)
        return res.get("albums", []) if res else []

    def get_songs(self, album_id: int | None = None) -> list:
        params = {"properties": ["duration", "track", "thumbnail"]}
        if album_id is not None:
            params["filter"] = {"albumid": album_id}
        res = self.rpc("AudioLibrary.GetSongs", params)
        return res.get("songs", []) if res else []

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
        return res.get("files", []) if res else []

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
            "properties": ["title", "artist", "album"],
        })
        items = res.get("items", []) if res else []
        return [
            {
                "position": idx,
                "title": it.get("title") or it.get("label") or "Pista sin titulo",
                "artist": ", ".join(it.get("artist", [])),
                "current": idx == current_position,
            }
            for idx, it in enumerate(items)
        ]

    def goto_position(self, position: int) -> None:
        players = self.rpc("Player.GetActivePlayers")
        if not players:
            return
        self.rpc("Player.GoTo", {"playerid": players[0]["playerid"], "to": position})

    def is_reachable(self) -> bool:
        return self.rpc("JSONRPC.Ping") == "pong"

    def has_audio_cd(self) -> bool:
        """True si Kodi detecta un CD de audio (Redbook/CDDA) reproducible
        en la unidad -- no confundir con un disco de datos con FLAC/MP3
        (esos se navegan como una fuente de archivos normal, no por aqui).
        XBMC.GetInfoBooleans, no System.GetInfoBooleans (probado en vivo:
        el namespace System.* da "Method not found" para esto en esta
        build de Kodi, el namespace legacy XBMC.* si funciona)."""
        res = self.rpc("XBMC.GetInfoBooleans", {"booleans": ["system.hasmediadvdaudio"]})
        return bool(res and res.get("system.hasmediadvdaudio"))

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
