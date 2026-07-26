import threading

import soundcard as sc

from ambar.ports.audio_level_source import OnSamples

SAMPLE_RATE = 48000
CHUNK_FRAMES = 1024


class WasapiLoopbackSource:
    """Captura la salida de audio del sistema en Windows via WASAPI loopback
    (paquete `soundcard`), sin necesidad de ningun driver adicional.

    NOTA: sin verificar en un mini PC/VM Windows real en esta sesion de
    trabajo (desarrollada en macOS) -- revisar al probar en el hardware de
    produccion.
    """

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self, on_samples: OnSamples) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, args=(on_samples,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self, on_samples: OnSamples) -> None:
        try:
            speaker = sc.default_speaker()
            mic = sc.get_microphone(id=speaker.id, include_loopback=True)
            with mic.recorder(samplerate=SAMPLE_RATE) as recorder:
                while self._running:
                    # soundcard entrega (numframes, nchannels): un canal por
                    # columna (izquierda/derecha), no mezclado.
                    data = recorder.record(numframes=CHUNK_FRAMES)
                    if data.ndim > 1:
                        channels = [data[:, i].tolist() for i in range(data.shape[1])]
                    else:
                        channels = [data.tolist()]
                    on_samples(channels)
        except Exception as e:
            print(f"VU-meter: captura de audio WASAPI no disponible ({e}); el medidor quedara inactivo.")
            self._running = False
