from ambar.application.system import SystemService


class FakeWindow:
    def __init__(self):
        self.calls = []

    def toggle_fullscreen(self):
        self.calls.append("toggle_fullscreen")

    def close(self):
        self.calls.append("close")


class FakeAudioLevelService:
    def __init__(self):
        self.calls = []

    def stop(self):
        self.calls.append("stop")


class FakeVolumeController:
    def __init__(self):
        self.calls = []

    def get(self):
        return {"level": 42, "muted": False}

    def set_level(self, level):
        self.calls.append(("set_level", level))

    def set_muted(self, muted):
        self.calls.append(("set_muted", muted))


class FakeKodiGateway:
    def __init__(self):
        self.calls = []

    def stop(self):
        self.calls.append("stop")


class FakeSpotifyGateway:
    def __init__(self):
        self.calls = []

    def pause(self):
        self.calls.append("pause")


def make_service(window=None, audio=None, volume=None, kodi=None, spotify=None):
    return SystemService(
        window or FakeWindow(),
        audio or FakeAudioLevelService(),
        volume or FakeVolumeController(),
        kodi or FakeKodiGateway(),
        spotify or FakeSpotifyGateway(),
    )


def test_get_volume_delegates_to_controller():
    volume = FakeVolumeController()
    service = make_service(volume=volume)

    assert service.get_volume() == {"level": 42, "muted": False}


def test_set_volume_level_delegates_to_controller():
    volume = FakeVolumeController()
    service = make_service(volume=volume)

    service.set_volume_level(70)

    assert volume.calls == [("set_level", 70)]


def test_set_volume_muted_delegates_to_controller():
    volume = FakeVolumeController()
    service = make_service(volume=volume)

    service.set_volume_muted(True)

    assert volume.calls == [("set_muted", True)]


def test_exit_stops_playback_before_closing_window():
    kodi, spotify = FakeKodiGateway(), FakeSpotifyGateway()
    audio, window = FakeAudioLevelService(), FakeWindow()
    service = make_service(window=window, audio=audio, kodi=kodi, spotify=spotify)

    service.execute("exit")

    assert kodi.calls == ["stop"]
    assert spotify.calls == ["pause"]
    assert audio.calls == ["stop"]
    assert window.calls == ["close"]
