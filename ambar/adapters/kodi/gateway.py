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
            "properties": ["percentage", "speed"],
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
        )

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
        res = self.rpc("Files.GetDirectory", {
            "directory": path,
            "media": "music",
            "properties": ["thumbnail", "file", "mimetype"],
        })
        return res.get("files", []) if res else []

    def play(self, item: dict) -> None:
        self.rpc("Playlist.Clear", {"playlistid": 0})
        self.rpc("Playlist.Add", {"playlistid": 0, "item": item})
        self.rpc("Player.Open", {"item": {"playlistid": 0}})

    def art_proxy(self, path: str) -> tuple[bytes | str, int, str | None]:
        img_url = f"http://{self.host}:{self.port}/image/{path}"
        try:
            r = requests.get(img_url, timeout=3)
            return r.content, r.status_code, r.headers.get("Content-Type", "image/jpeg")
        except Exception:
            return "", 404, None
