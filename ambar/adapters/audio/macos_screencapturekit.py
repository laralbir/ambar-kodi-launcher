import array
import threading

import CoreMedia as CM
import objc
import ScreenCaptureKit as SCK

from ambar.ports.audio_level_source import OnSamples

_CAPTURE_TIMEOUT_SECONDS = 10


class ScreenCaptureKitAudioSource:
    """Captura el audio de salida del sistema en macOS via ScreenCaptureKit
    (macOS 13+), sin necesidad de ningun driver virtual.

    La primera vez que se usa, macOS pide permiso de "Grabacion de pantalla"
    (System Settings > Privacy & Security). Si se deniega, o si algo falla al
    montar el stream, `start()` simplemente no llega a emitir muestras nunca
    -- el resto de la app sigue funcionando y el VU-metro queda inactivo.

    Nota de implementacion: la extraccion de PCM usa
    CMBlockBufferCopyDataBytes (no CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer,
    cuyos metadatos de bridging de PyObjC para el struct AudioBufferList de
    salida no funcionan en pyobjc-framework-CoreMedia 12.2.1 -- se probo
    exhaustivamente: bytearray/ctypes/NSMutableData/objc.createStructType,
    todas rechazadas con "depythonifying 'pointer'"). CMBlockBufferCopyDataBytes
    si esta correctamente anotado (o^v con c_array_length_in_arg) y devuelve
    los bytes ya copiados en la tupla de retorno.
    """

    def __init__(self):
        self._stream = None
        self._delegate = None
        self._running = False

    def start(self, on_samples: OnSamples) -> None:
        self._running = True
        threading.Thread(target=self._run, args=(on_samples,), daemon=True).start()

    def stop(self) -> None:
        self._running = False
        stream, self._stream = self._stream, None
        if stream is not None:
            stop_done = threading.Event()
            try:
                stream.stopCaptureWithCompletionHandler_(lambda e: stop_done.set())
                stop_done.wait(5)
            except Exception:
                pass
        self._delegate = None

    def _run(self, on_samples: OnSamples) -> None:
        try:
            display = self._get_first_display()
            content_filter = SCK.SCContentFilter.alloc().initWithDisplay_excludingWindows_(display, [])

            config = SCK.SCStreamConfiguration.alloc().init()
            config.setCapturesAudio_(True)
            config.setChannelCount_(2)
            # ScreenCaptureKit exige tambien capturar video; lo pedimos minimo.
            config.setWidth_(2)
            config.setHeight_(2)
            config.setMinimumFrameInterval_(CM.CMTimeMake(1, 10))

            self._delegate = _AudioDelegate.alloc().initWithCallback_channels_(on_samples, 2)
            self._stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(
                content_filter, config, self._delegate
            )
            ok, err = self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
                self._delegate, SCK.SCStreamOutputTypeAudio, None, None
            )
            if not ok:
                raise RuntimeError(f"no se pudo registrar el output de audio: {err}")

            self._start_capture()
        except Exception as e:
            print(f"VU-meter: captura de audio en macOS no disponible ({e}); el medidor quedara inactivo.")
            self._running = False

    def _get_first_display(self):
        done = threading.Event()
        result = {}

        def content_handler(content, error):
            result["content"] = content
            result["error"] = error
            done.set()

        SCK.SCShareableContent.getShareableContentWithCompletionHandler_(content_handler)
        if not done.wait(_CAPTURE_TIMEOUT_SECONDS):
            raise RuntimeError("timeout esperando contenido compartible")
        if result.get("error") or not result.get("content"):
            raise RuntimeError(f"no se pudo obtener contenido compartible ({result.get('error')})")
        displays = result["content"].displays()
        if not displays:
            raise RuntimeError("no se encontro ninguna pantalla")
        return displays[0]

    def _start_capture(self) -> None:
        start_done = threading.Event()
        result = {}

        def start_handler(error):
            result["error"] = error
            start_done.set()

        self._stream.startCaptureWithCompletionHandler_(start_handler)
        if not start_done.wait(_CAPTURE_TIMEOUT_SECONDS):
            raise RuntimeError("timeout arrancando la captura")
        if result.get("error"):
            raise RuntimeError(f"no se pudo arrancar la captura ({result['error']}) -- ¿permiso de Grabacion de pantalla denegado?")


class _AudioDelegate(objc.lookUpClass("NSObject")):
    def initWithCallback_channels_(self, callback, channel_count):
        self = objc.super(_AudioDelegate, self).init()
        if self is None:
            return None
        self._callback = callback
        self._channel_count = channel_count
        return self

    def stream_didOutputSampleBuffer_ofType_(self, stream, sample_buffer, output_type):
        if output_type != SCK.SCStreamOutputTypeAudio:
            return
        try:
            data_buffer = CM.CMSampleBufferGetDataBuffer(sample_buffer)
            if not data_buffer:
                return
            length = CM.CMBlockBufferGetDataLength(data_buffer)
            status, data_bytes = CM.CMBlockBufferCopyDataBytes(data_buffer, 0, length, None)
            if status != 0 or not data_bytes:
                return
            samples = array.array("f")
            samples.frombytes(data_bytes)
            if not samples:
                return
            # ScreenCaptureKit entrega audio PCM "planar" (no intercalado):
            # el buffer trae el canal 0 completo seguido del canal 1 completo,
            # NO muestras L/R alternadas. Verificado en vivo con el ASBD
            # (kAudioFormatFlagIsNonInterleaved) y comparando longitudes.
            n = len(samples)
            per_channel = n // self._channel_count
            if per_channel == 0:
                return
            channels = [
                samples[i * per_channel:(i + 1) * per_channel] for i in range(self._channel_count)
            ]
            self._callback(channels)
        except Exception:
            pass

    def stream_didStopWithError_(self, stream, error):
        pass
