from ambar.application.audio_level import AudioLevelService
from ambar.application.events import EventBus


class FakeAudioLevelSource:
    def start(self, on_samples):
        pass

    def stop(self):
        pass


def test_set_smoothing_updates_existing_meters():
    service = AudioLevelService(FakeAudioLevelSource(), EventBus(), attack_seconds=0.4, release_seconds=0.4)
    service._on_samples([[0.0] * 10, [0.0] * 10])  # crea los LevelMeter (uno por canal)

    service.set_smoothing(attack_seconds=0.02, release_seconds=0.02)

    for meter in service._meters:
        assert meter._attack_seconds == 0.02
        assert meter._release_seconds == 0.02


def test_set_smoothing_before_any_meter_exists_does_not_error():
    service = AudioLevelService(FakeAudioLevelSource(), EventBus())

    service.set_smoothing(attack_seconds=0.02, release_seconds=0.02)  # no debe lanzar

    assert service._attack_seconds == 0.02
