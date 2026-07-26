from dataclasses import asdict

from ambar.domain.events import AudioLevelChanged, PlaybackStateChanged


class SocketIOBridge:
    """Unico adapter que sabe que el transporte de eventos hacia el frontend es
    SocketIO: traduce eventos de dominio -> socketio.emit(...)."""

    def __init__(self, socketio):
        self._socketio = socketio

    def handle_playback_state_changed(self, event: PlaybackStateChanged) -> None:
        self._socketio.emit("playback_update", asdict(event.state))

    def handle_audio_level_changed(self, event: AudioLevelChanged) -> None:
        self._socketio.emit("audio_level", {"db": event.db})
