from ambar.domain.playback import PlaybackState

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False


SPOTIFY_SCOPE = (
    "user-read-playback-state user-modify-playback-state "
    "playlist-read-private playlist-read-collaborative user-library-read"
)


class SpotifyGateway:
    """Adapter hacia la Web API de Spotify (Spotipy). Se reconfigura en caliente
    cuando cambian las credenciales en Ajustes."""

    def __init__(self, cache_path: str):
        self._cache_path = cache_path
        self._oauth: "SpotifyOAuth | None" = None

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
        token_info = self._oauth.get_cached_token()
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
                "current": True,
            })
        for item in data.get("queue", []):
            playlist.append({
                "title": item.get("name", ""),
                "artist": ", ".join(a["name"] for a in item.get("artists", [])),
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
            progress=int(100 * current.get("progress_ms", 0) / duration),
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
            return res.get("items", [])
        except Exception:
            return []

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
        if sp:
            try:
                sp.start_playback(context_uri=context_uri)
            except Exception:
                pass
        return True

    def play_track(self, uri: str | None) -> bool:
        if not self._oauth or not uri:
            return False
        sp = self._client()
        if sp:
            try:
                sp.start_playback(uris=[uri])
            except Exception:
                pass
        return True

    def get_authorize_url(self) -> str | None:
        return self._oauth.get_authorize_url() if self._oauth else None

    def exchange_code(self, code: str | None) -> bool:
        if not self._oauth or not code:
            return False
        self._oauth.get_access_token(code, as_dict=False)
        return True
