from dataclasses import dataclass, field

from ambar.domain.playback import PlaybackState


@dataclass
class PlaybackStateChanged:
    state: PlaybackState


@dataclass
class AudioLevelChanged:
    # Un valor de dB por canal, ej. [izquierda, derecha]. Al menos 1 elemento.
    db: list[float] = field(default_factory=list)
    # Espectómetro/osciloscopio (ver domain/audio.py SpectrumAnalyzer).
    # spectrum: un espectro por canal (igual forma que db, ej.
    # [izquierda, derecha]), cada uno una lista de bandas normalizadas
    # 0..1. waveform: mono (mezcla de todos los canales), normalizado
    # -1..1 por muestra -- ver AudioLevelService para el porqué de la
    # asimetría estéreo/mono entre los dos.
    spectrum: list[list[float]] = field(default_factory=list)
    waveform: list[float] = field(default_factory=list)
