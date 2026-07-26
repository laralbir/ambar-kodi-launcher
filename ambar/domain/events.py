from dataclasses import dataclass, field

from ambar.domain.playback import PlaybackState


@dataclass
class PlaybackStateChanged:
    state: PlaybackState


@dataclass
class AudioLevelChanged:
    # Un valor de dB por canal, ej. [izquierda, derecha]. Al menos 1 elemento.
    db: list[float] = field(default_factory=list)
