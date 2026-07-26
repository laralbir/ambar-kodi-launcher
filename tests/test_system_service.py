from ambar.application.system import SystemService


class FakeWindow:
    def toggle_fullscreen(self):
        pass

    def close(self):
        pass


class FakeAudioLevelService:
    def stop(self):
        pass


class FakeVolumeController:
    def __init__(self):
        self.calls = []

    def get(self):
        return {"level": 42, "muted": False}

    def set_level(self, level):
        self.calls.append(("set_level", level))

    def set_muted(self, muted):
        self.calls.append(("set_muted", muted))


def test_get_volume_delegates_to_controller():
    volume = FakeVolumeController()
    service = SystemService(FakeWindow(), FakeAudioLevelService(), volume)

    assert service.get_volume() == {"level": 42, "muted": False}


def test_set_volume_level_delegates_to_controller():
    volume = FakeVolumeController()
    service = SystemService(FakeWindow(), FakeAudioLevelService(), volume)

    service.set_volume_level(70)

    assert volume.calls == [("set_level", 70)]


def test_set_volume_muted_delegates_to_controller():
    volume = FakeVolumeController()
    service = SystemService(FakeWindow(), FakeAudioLevelService(), volume)

    service.set_volume_muted(True)

    assert volume.calls == [("set_muted", True)]
