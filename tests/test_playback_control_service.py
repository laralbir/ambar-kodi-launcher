from ambar.application.playback_control import PlaybackControlService


class FakeSource:
    def __init__(self):
        self.calls = []

    def control(self, action):
        self.calls.append(("control", action))

    def seek(self, percentage):
        self.calls.append(("seek", percentage))


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
