from ambar.application.events import EventBus
from ambar.application.now_playing import NowPlayingService
from ambar.domain.events import PlaybackStateChanged
from ambar.domain.playback import PlaybackState


class FakeSource:
    def __init__(self, state: PlaybackState | None = None, playlist: list | None = None):
        self._state = state
        self._playlist = playlist if playlist is not None else []
        self.pause_calls = 0

    def get_state(self):
        return self._state

    def control(self, action):
        pass

    def pause(self):
        self.pause_calls += 1

    def get_playlist(self):
        return self._playlist


def test_kodi_wins_over_spotify_when_both_active():
    kodi = FakeSource(PlaybackState(source="kodi", playing=True, title="A"))
    spotify = FakeSource(PlaybackState(source="spotify", playing=True, title="B"))
    service = NowPlayingService(kodi, spotify, EventBus())

    state = service.get_state()

    assert state.source == "kodi"
    assert state.title == "A"


def test_falls_back_to_spotify_when_kodi_idle():
    kodi = FakeSource(None)
    spotify = FakeSource(PlaybackState(source="spotify", playing=True, title="B"))
    service = NowPlayingService(kodi, spotify, EventBus())

    state = service.get_state()

    assert state.source == "spotify"
    assert state.title == "B"


def test_empty_state_when_nothing_playing():
    service = NowPlayingService(FakeSource(None), FakeSource(None), EventBus())

    state = service.get_state()

    assert state.source is None
    assert state.playing is False


def test_publish_current_state_emits_on_event_bus():
    kodi = FakeSource(PlaybackState(source="kodi", playing=True, title="A"))
    bus = EventBus()
    received = []
    bus.subscribe(PlaybackStateChanged, received.append)
    service = NowPlayingService(kodi, FakeSource(None), bus)

    service.publish_current_state()

    assert len(received) == 1
    assert received[0].state.source == "kodi"


def test_poll_spotify_skips_when_kodi_is_last_known_source():
    kodi = FakeSource(PlaybackState(source="kodi", playing=True))
    spotify = FakeSource(PlaybackState(source="spotify", playing=True))
    bus = EventBus()
    received = []
    bus.subscribe(PlaybackStateChanged, received.append)
    service = NowPlayingService(kodi, spotify, bus)

    service.get_state()  # establece last_source = "kodi"
    service.poll_spotify()

    assert received == []


def test_poll_spotify_emits_when_kodi_not_last_known_source():
    spotify = FakeSource(PlaybackState(source="spotify", playing=True))
    bus = EventBus()
    received = []
    bus.subscribe(PlaybackStateChanged, received.append)
    service = NowPlayingService(FakeSource(None), spotify, bus)

    service.poll_spotify()

    assert len(received) == 1
    assert received[0].state.source == "spotify"


def test_get_playlist_from_kodi_when_kodi_is_source():
    kodi_playlist = [{"title": "A", "artist": "X", "current": True}]
    kodi = FakeSource(PlaybackState(source="kodi", playing=True), playlist=kodi_playlist)
    service = NowPlayingService(kodi, FakeSource(None), EventBus())

    assert service.get_playlist() == kodi_playlist


def test_get_playlist_from_spotify_when_spotify_is_source():
    spotify_playlist = [{"title": "B", "artist": "Y", "current": True}]
    spotify = FakeSource(PlaybackState(source="spotify", playing=True), playlist=spotify_playlist)
    service = NowPlayingService(FakeSource(None), spotify, EventBus())

    assert service.get_playlist() == spotify_playlist


def test_get_playlist_empty_when_nothing_playing():
    service = NowPlayingService(FakeSource(None), FakeSource(None), EventBus())

    assert service.get_playlist() == []


def test_enforce_single_source_pauses_spotify_when_kodi_starts_while_spotify_playing():
    kodi = FakeSource(PlaybackState(source="kodi", playing=True))
    spotify = FakeSource(PlaybackState(source="spotify", playing=True))
    service = NowPlayingService(kodi, spotify, EventBus())

    service.enforce_single_source()

    assert spotify.pause_calls == 1
    assert kodi.pause_calls == 0


def test_enforce_single_source_pauses_kodi_when_spotify_starts_while_kodi_playing():
    kodi = FakeSource(PlaybackState(source="kodi", playing=True))
    spotify = FakeSource(PlaybackState(source="spotify", playing=True))
    service = NowPlayingService(kodi, spotify, EventBus())
    # Kodi ya estaba sonando de antes (no es una transicion nueva) --
    # Spotify es quien acaba de empezar.
    service._kodi_was_playing = True

    service.enforce_single_source()

    assert kodi.pause_calls == 1
    assert spotify.pause_calls == 0


def test_enforce_single_source_does_nothing_when_only_one_source_playing():
    kodi = FakeSource(PlaybackState(source="kodi", playing=True))
    spotify = FakeSource(None)
    service = NowPlayingService(kodi, spotify, EventBus())

    service.enforce_single_source()

    assert kodi.pause_calls == 0
    assert spotify.pause_calls == 0


def test_enforce_single_source_does_nothing_once_both_already_playing_continuously():
    kodi = FakeSource(PlaybackState(source="kodi", playing=True))
    spotify = FakeSource(PlaybackState(source="spotify", playing=True))
    service = NowPlayingService(kodi, spotify, EventBus())

    service.enforce_single_source()  # primera vez: kodi "empieza", pausa spotify
    spotify.pause_calls = 0
    kodi.pause_calls = 0
    service.enforce_single_source()  # segunda vez: ninguna transicion nueva

    assert kodi.pause_calls == 0
    assert spotify.pause_calls == 0
