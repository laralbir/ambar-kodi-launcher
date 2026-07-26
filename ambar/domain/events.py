from dataclasses import dataclass

from ambar.domain.playback import PlaybackState


@dataclass
class PlaybackStateChanged:
    state: PlaybackState
