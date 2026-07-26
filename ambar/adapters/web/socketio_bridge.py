from dataclasses import asdict

from ambar.domain.events import PlaybackStateChanged


class SocketIOBridge:
    """Unico adapter que sabe que el transporte de eventos hacia el frontend es
    SocketIO: traduce PlaybackStateChanged -> socketio.emit("playback_update", ...)."""

    def __init__(self, socketio):
        self._socketio = socketio

    def handle_playback_state_changed(self, event: PlaybackStateChanged) -> None:
        self._socketio.emit("playback_update", asdict(event.state))
