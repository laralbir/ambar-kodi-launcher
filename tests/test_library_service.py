from ambar.application.library import LibraryService


class FakeKodiGateway:
    def __init__(self, reachable=True):
        self.calls = []
        self._reachable = reachable

    def stop(self):
        self.calls.append("stop")

    def play(self, item):
        self.calls.append(("play", item))

    def is_reachable(self):
        return self._reachable


class FakeSpotifyGateway:
    def __init__(self, configured=True):
        self.calls = []
        self._configured = configured

    def pause(self):
        self.calls.append("pause")

    def play_context(self, context_uri):
        self.calls.append(("play_context", context_uri))
        return True

    def play_track(self, uri):
        self.calls.append(("play_track", uri))
        return True

    def get_playlist_tracks(self, playlist_id):
        self.calls.append(("get_playlist_tracks", playlist_id))
        return [{"title": "T", "artist": "A", "uri": "spotify:track:x", "duration": 120}]

    def is_configured(self):
        return self._configured


def test_kodi_play_pauses_spotify_before_playing():
    kodi = FakeKodiGateway()
    spotify = FakeSpotifyGateway()
    service = LibraryService(kodi, spotify)

    service.kodi_play({"songid": 1})

    assert spotify.calls == ["pause"]
    assert kodi.calls == [("play", {"songid": 1})]


def test_spotify_play_stops_kodi_before_playing():
    kodi = FakeKodiGateway()
    spotify = FakeSpotifyGateway()
    service = LibraryService(kodi, spotify)

    ok = service.spotify_play("spotify:playlist:abc")

    assert ok is True
    assert kodi.calls == ["stop"]
    assert spotify.calls == [("play_context", "spotify:playlist:abc")]


def test_kodi_play_works_when_spotify_not_configured():
    kodi = FakeKodiGateway()

    class UnconfiguredSpotify:
        def pause(self):
            pass  # best-effort, no-op sin credenciales

    service = LibraryService(kodi, UnconfiguredSpotify())

    service.kodi_play({"file": "cdda://local/"})

    assert kodi.calls == [("play", {"file": "cdda://local/"})]


def test_spotify_play_works_when_kodi_not_running():
    spotify = FakeSpotifyGateway()

    class UnreachableKodi:
        def stop(self):
            pass  # best-effort, no-op si Kodi no responde

    service = LibraryService(UnreachableKodi(), spotify)

    ok = service.spotify_play("spotify:playlist:abc")

    assert ok is True
    assert spotify.calls == [("play_context", "spotify:playlist:abc")]


def test_kodi_status_reflects_reachability():
    service = LibraryService(FakeKodiGateway(reachable=False), FakeSpotifyGateway())

    assert service.kodi_status() == {"available": False}


def test_spotify_status_reflects_configuration():
    service = LibraryService(FakeKodiGateway(), FakeSpotifyGateway(configured=False))

    assert service.spotify_status() == {"available": False}


def test_kodi_play_with_artistid_plays_whole_artist():
    kodi = FakeKodiGateway()
    service = LibraryService(kodi, FakeSpotifyGateway())

    service.kodi_play({"artistid": 7})

    assert kodi.calls == [("play", {"artistid": 7})]


def test_kodi_play_with_directory_uses_directory_not_file():
    # Playlist.Add con "file" apuntando a una carpeta da "Invalid params" en
    # Kodi -- una carpeta/CD entero se reproduce con "directory", verificado
    # en vivo contra Kodi real.
    kodi = FakeKodiGateway()
    service = LibraryService(kodi, FakeSpotifyGateway())

    service.kodi_play({"directory": "/Users/carlos/Music/"})

    assert kodi.calls == [("play", {"directory": "/Users/carlos/Music/"})]


def test_spotify_playlist_tracks_delegates_to_gateway():
    spotify = FakeSpotifyGateway()
    service = LibraryService(FakeKodiGateway(), spotify)

    tracks = service.spotify_playlist_tracks("playlist123")

    assert tracks == [{"title": "T", "artist": "A", "uri": "spotify:track:x", "duration": 120}]
    assert spotify.calls == [("get_playlist_tracks", "playlist123")]


def test_spotify_playlist_tracks_empty_without_playlist_id():
    service = LibraryService(FakeKodiGateway(), FakeSpotifyGateway())

    assert service.spotify_playlist_tracks(None) == []


def test_spotify_play_track_stops_kodi_before_playing():
    kodi = FakeKodiGateway()
    spotify = FakeSpotifyGateway()
    service = LibraryService(kodi, spotify)

    ok = service.spotify_play_track("spotify:track:x")

    assert ok is True
    assert kodi.calls == ["stop"]
    assert spotify.calls == [("play_track", "spotify:track:x")]
