from ambar.adapters.kodi.gateway import KodiGateway
from ambar.adapters.spotify.gateway import SpotifyGateway


class LibraryService:
    """Orquesta la navegacion de biblioteca nativa de Kodi y las playlists de Spotify."""

    def __init__(self, kodi_gateway: KodiGateway, spotify_gateway: SpotifyGateway):
        self._kodi = kodi_gateway
        self._spotify = spotify_gateway

    def kodi_artists(self) -> list:
        return self._kodi.get_artists()

    def kodi_albums(self, artist_id: int | None) -> list:
        return self._kodi.get_albums(artist_id)

    def kodi_songs(self, album_id: int | None) -> list:
        return self._kodi.get_songs(album_id)

    def kodi_directory(self, path: str) -> list:
        return self._kodi.get_directory(path)

    def kodi_play(self, body: dict) -> None:
        item = {}
        if "songid" in body:
            item["songid"] = body["songid"]
        elif "albumid" in body:
            item["albumid"] = body["albumid"]
        elif "file" in body:
            item["file"] = body["file"]
        self._kodi.play(item)

    def spotify_playlists(self) -> list:
        return self._spotify.get_playlists()

    def spotify_play(self, context_uri: str | None) -> bool:
        return self._spotify.play_context(context_uri)
