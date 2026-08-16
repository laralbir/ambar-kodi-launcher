import math
import time
from dataclasses import dataclass
from typing import Sequence

import numpy as np

DB_FLOOR = -60.0
DB_CEILING = 0.0
SPECTRUM_BANDS = 20
WAVEFORM_POINTS = 96
# Ballistica asimetrica: subida rapida para que se note la respuesta al
# instante (no como un VU analogico "de verdad", que resultaba demasiado
# lento/estatico en pantalla), bajada lenta tipo VU clasico (ANSI C16.5,
# ~300ms) para que siga cayendo "a la antigua" cuando el audio calla.
VU_ATTACK_SECONDS = 0.08
VU_RELEASE_SECONDS = 0.3

# Presets de "fluidez" configurables desde Ajustes: escalan la misma
# ballistica asimetrica de arriba. "fast" reacciona casi al instante (mas
# nervioso/vivo, sigue de cerca cada transitorio); "smooth" es mas lento y
# amortiguado (movimiento mas fluido/cinematografico, menos fiel al pico
# exacto). "normal" son las constantes de siempre.
#
# throttle_hz (frecuencia de publicacion por WebSocket, ver AudioLevelService)
# tambien escala por preset -- antes era fija a 20Hz siempre, asi que "fast"
# tenia una ballistica mas agil por dentro pero el frontend solo veia una
# muestra cada 50ms igual que "normal", y el movimiento no se notaba mas de
# verdad. Confirmado en vivo: subir throttle_hz en "fast" (mas muestras
# distintas llegando al frontend) es lo que de verdad hace notarse el
# movimiento, no solo estrechar attack/release.
VU_SMOOTHING_PRESETS = {
    "fast": {"attack": 0.02, "release": 0.1, "throttle_hz": 30.0},
    "normal": {"attack": VU_ATTACK_SECONDS, "release": VU_RELEASE_SECONDS, "throttle_hz": 20.0},
    "smooth": {"attack": 0.18, "release": 0.7, "throttle_hz": 15.0},
}


@dataclass
class AudioLevel:
    db: float


class LevelMeter:
    """Convierte fragmentos de muestras PCM (mono, floats en -1..1) en dBFS,
    con ballistica de ataque/liberacion asimetrica: sube rapido (respuesta
    inmediata a la musica) y baja despacio (efecto VU-metro clasico) en vez
    de saltar/pegarse con cada fragmento de audio."""

    def __init__(self, attack_seconds: float = VU_ATTACK_SECONDS, release_seconds: float = VU_RELEASE_SECONDS):
        self._attack_seconds = attack_seconds
        self._release_seconds = release_seconds
        self._smoothed_db = DB_FLOOR
        self._last_update: float | None = None

    def set_ballistics(self, attack_seconds: float, release_seconds: float) -> None:
        self._attack_seconds = attack_seconds
        self._release_seconds = release_seconds

    def update(self, samples: Sequence[float]) -> float:
        raw_db = self._rms_db(samples)
        tau = self._attack_seconds if raw_db > self._smoothed_db else self._release_seconds

        now = time.monotonic()
        dt = tau if self._last_update is None else now - self._last_update
        self._last_update = now

        alpha = 1 - math.exp(-dt / tau) if tau > 0 else 1
        self._smoothed_db += alpha * (raw_db - self._smoothed_db)
        return self._smoothed_db

    @staticmethod
    def _rms_db(samples: Sequence[float]) -> float:
        if not samples:
            return DB_FLOOR
        mean_square = sum(s * s for s in samples) / len(samples)
        if mean_square <= 0:
            return DB_FLOOR
        db = 10 * math.log10(mean_square)  # 20*log10(rms) == 10*log10(rms**2)
        return max(DB_FLOOR, min(DB_CEILING, db))


class SpectrumAnalyzer:
    """Espectómetro (barras de frecuencia) y osciloscopio (forma de onda)
    para el VU-metro, a partir del mismo fragmento de muestras PCM que ya
    usa LevelMeter -- no captura audio aparte, solo lo reanaliza. Sin
    ballistica propia (a diferencia de LevelMeter): con un fragmento
    nuevo cada ~20ms (1024 muestras/48kHz) ya se ve "vivo" de por si,
    suavizarlo mas lo dejaba con pinta de ir a cámara lenta.

    NO calibrado contra hardware de audio real (desarrollado sin poder
    reproducir sonido real por WASAPI en esta sesión) -- REF_DIVISOR
    (magnitud FFT aproximada de un tono a escala completa tras la
    ventana de Hann, sobre la que se calcula el 0dB del espectómetro) es
    una estimación teórica, no medida en vivo. Si las barras del
    espectómetro salen siempre al máximo o siempre vacías con audio real,
    revisar/ajustar este valor primero."""

    REF_DIVISOR = 4.0

    @staticmethod
    def spectrum(samples: Sequence[float], bands: int = SPECTRUM_BANDS) -> list[float]:
        n = len(samples)
        if n < 2:
            return [0.0] * bands
        arr = np.asarray(samples, dtype=np.float64)
        magnitudes = np.abs(np.fft.rfft(arr * np.hanning(n)))
        usable = magnitudes[1:]  # descarta el bin 0 (DC, sin interes visual)
        total = len(usable)
        if total < bands:
            return [0.0] * bands
        ref = n / SpectrumAnalyzer.REF_DIVISOR
        result = []
        prev_edge = 0
        for i in range(1, bands + 1):
            # Bordes de banda espaciados logaritmicamente sobre el INDICE
            # del bin (no en Hz -- los adapters de audio no exponen la
            # frecuencia de muestreo real, ver AudioLevelSource): el
            # efecto perceptual es el mismo que espaciar por Hz, ya que
            # el indice del bin ya es proporcional a la frecuencia --
            # graves ocupan mas barras, agudos se comprimen en menos,
            # como en cualquier espectómetro "normal".
            edge = min(total, max(prev_edge + 1, round(total ** (i / bands))))
            band = usable[prev_edge:edge]
            prev_edge = edge
            energy = float(band.mean()) if band.size else 0.0
            db = 20 * math.log10(energy / ref) if energy > 0 else DB_FLOOR
            db = max(DB_FLOOR, min(DB_CEILING, db))
            result.append((db - DB_FLOOR) / (DB_CEILING - DB_FLOOR))
        return result

    @staticmethod
    def waveform(samples: Sequence[float], points: int = WAVEFORM_POINTS) -> list[float]:
        n = len(samples)
        if n == 0:
            return [0.0] * points
        if n <= points:
            return list(samples)
        # Decimacion simple por zancada -- un osciloscopio decorativo no
        # necesita anti-aliasing de verdad, solo dar la forma general de
        # la onda.
        arr = np.asarray(samples, dtype=np.float64)
        idx = np.linspace(0, n - 1, points).astype(int)
        return arr[idx].tolist()
