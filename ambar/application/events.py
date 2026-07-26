from collections import defaultdict
from typing import Callable


class EventBus:
    """Bus de eventos de dominio en proceso (pub/sub sincrono).

    Desacopla a quien detecta un cambio (los listeners de Kodi/Spotify) de
    quien lo emite hacia el exterior (el bridge de SocketIO).
    """

    def __init__(self):
        self._subscribers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: object) -> None:
        for handler in self._subscribers[type(event)]:
            handler(event)
