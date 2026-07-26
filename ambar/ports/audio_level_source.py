from typing import Callable, Protocol, Sequence

# Un fragmento de muestras PCM (floats en -1..1) por canal, ej. [izquierda, derecha].
OnSamples = Callable[[Sequence[Sequence[float]]], None]


class AudioLevelSource(Protocol):
    """Puerto hacia la captura de audio del sistema (loopback), para medir el
    nivel real de la señal que se está reproduciendo. Al menos estereo: cada
    llamada a on_samples entrega una lista con un fragmento de muestras por
    canal (2 para estereo, podrian ser mas)."""

    def start(self, on_samples: OnSamples) -> None: ...

    def stop(self) -> None: ...
