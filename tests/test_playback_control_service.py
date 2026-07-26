from ambar.application.playback_control import PlaybackControlService


class FakeSource:
    def __init__(self):
        self.calls = []

    def control(self, action):
        self.calls.append(("control", action))

    def seek(self, percentage):
        self.calls.append(("seek", percentage))

    def goto_position(self, position):
        self.calls.append(("goto_position", position))

    def play_track(self, uri):
        self.calls.append(("play_track", uri))


def test_execute_routes_to_kodi():
    kodi, spotify = FakeSource(), FakeSource()
    service = PlaybackControlService(kodi, spotify)

    service.execute("kodi", "playpause")

    assert kodi.calls == [("control", "playpause")]
    assert spotify.calls == []


def test_execute_routes_to_spotify():
    kodi, spotify = FakeSource(), FakeSource()
    service = PlaybackControlService(kodi, spotify)

    service.execute("spotify", "next")

    assert spotify.calls == [("control", "next")]
    assert kodi.calls == []


def test_execute_ignores_unknown_source():
    kodi, spotify = FakeSource(), FakeSource()
    service = PlaybackControlService(kodi, spotify)

    service.execute(None, "playpause")
    service.execute("vlc", "playpause")

    assert kodi.calls == []
    assert spotify.calls == []


def test_seek_routes_to_kodi():
    kodi, spotify = FakeSource(), FakeSource()
    service = PlaybackControlService(kodi, spotify)

    service.seek("kodi", 42.5)

    assert kodi.calls == [("seek", 42.5)]
    assert spotify.calls == []


def test_seek_routes_to_spotify():
    kodi, spotify = FakeSource(), FakeSource()
    service = PlaybackControlService(kodi, spotify)

    service.seek("spotify", 10)

    assert spotify.calls == [("seek", 10)]
    assert kodi.calls == []


def test_play_playlist_item_routes_to_kodi_by_position():
    kodi, spotify = FakeSource(), FakeSource()
    service = PlaybackControlService(kodi, spotify)

    service.play_playlist_item("kodi", 4, None)

    assert kodi.calls == [("goto_position", 4)]
    assert spotify.calls == []


def test_play_playlist_item_routes_to_spotify_by_uri():
    kodi, spotify = FakeSource(), FakeSource()
    service = PlaybackControlService(kodi, spotify)

    service.play_playlist_item("spotify", None, "spotify:track:abc")

    assert spotify.calls == [("play_track", "spotify:track:abc")]
    assert kodi.calls == []


def test_play_playlist_item_kodi_position_zero_is_valid():
    # position=0 es "falsy" en Python -- asegurar que no se trata como
    # "sin posicion" con un chequeo tipo `if position` en vez de `is not None`.
    kodi, spotify = FakeSource(), FakeSource()
    service = PlaybackControlService(kodi, spotify)

    service.play_playlist_item("kodi", 0, None)

    assert kodi.calls == [("goto_position", 0)]
