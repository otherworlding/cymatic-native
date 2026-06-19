"""
System audio capture via ScreenCaptureKit (macOS 12.3+).

Captures ALL audio playing on the Mac — Apple Music, Spotify, browser video,
any app — and feeds it to the visualizer without any virtual audio driver.

Requires: Screen Recording permission (System Settings → Privacy & Security →
           Screen Recording → enable for Terminal or your app)
"""

import ctypes
import threading
import numpy as np
from numpy.fft import rfft

import objc
from Foundation import NSObject, NSRunLoop, NSDate
import ScreenCaptureKit as SCK
import CoreMedia as CM

from .config import FFT_SIZE, SAMPLE_RATE

# ── libdispatch for creating the audio callback queue ────────────────────────
_libdispatch = ctypes.CDLL('/usr/lib/system/libdispatch.dylib')
_libdispatch.dispatch_queue_create.restype  = ctypes.c_void_p
_libdispatch.dispatch_queue_create.argtypes = [ctypes.c_char_p, ctypes.c_void_p]

_SCStreamOutputType_Audio = 1   # SCStreamOutputTypeAudio enum value

# ── Stream output delegate ────────────────────────────────────────────────────
_proto = objc.protocolNamed('SCStreamOutput')


class _Output(NSObject, protocols=[_proto]):
    """Receives CMSampleBuffers from SCStream and converts them to FFT data."""

    @objc.python_method
    def configure(self, push_fn):
        self._push = push_fn
        self._win  = np.hanning(FFT_SIZE)
        self._buf  = np.zeros(FFT_SIZE, dtype=np.float32)

    def stream_didOutputSampleBuffer_ofType_(self, stream, sample_buffer, output_type):
        if output_type != _SCStreamOutputType_Audio:
            return
        try:
            self._handle(sample_buffer)
        except Exception:
            pass

    @objc.python_method
    def _handle(self, sample_buffer):
        # Pull raw PCM bytes out of the CMSampleBuffer block buffer
        block = CM.CMSampleBufferGetDataBuffer(sample_buffer)
        if block is None:
            return

        # CMBlockBufferGetDataPointer(buf, offset, lengthAtOffsetOut,
        #                             totalLengthOut, dataPointerOut)
        result = CM.CMBlockBufferGetDataPointer(block, 0, None, None, None)
        # pyobjc returns (status, lengthAtOffset, totalLength, dataPointer)
        if result[0] != 0:  # kCMBlockBufferNoErr = 0
            return

        total_bytes = result[2]
        data_ptr    = result[3]   # ctypes address as int

        if not total_bytes or not data_ptr:
            return

        # ScreenCaptureKit delivers float32 samples
        n_samples = total_bytes // 4
        arr = np.frombuffer(
            (ctypes.c_float * n_samples).from_address(int(data_ptr)),
            dtype=np.float32,
        ).copy()

        # Rolling buffer → FFT
        n = len(arr)
        if n >= FFT_SIZE:
            self._buf = arr[-FFT_SIZE:]
        else:
            self._buf = np.roll(self._buf, -n)
            self._buf[-n:] = arr[:FFT_SIZE] if n >= FFT_SIZE else arr

        fft = np.abs(rfft(self._buf * self._win))
        self._push(fft)


# ── Public class ──────────────────────────────────────────────────────────────

class SystemAudioCapture:
    """
    One-click system audio capture — no BlackHole needed.
    Usage:
        cap = SystemAudioCapture(push_fn)   # push_fn(fft_array)
        ok  = cap.start()                   # True if permission granted
        cap.stop()
    """

    def __init__(self, push_fn):
        self._push    = push_fn
        self._stream  = None
        self._output  = None
        self._thread  = None
        self._ready   = threading.Event()
        self._error   = None
        self.current_sr = SAMPLE_RATE

    def start(self) -> bool:
        self._thread = threading.Thread(target=self._run, daemon=True, name='sc-audio')
        self._thread.start()
        self._ready.wait(timeout=12)
        return self._error is None

    def stop(self):
        if self._stream:
            self._stream.stopCaptureWithCompletionHandler_(lambda _: None)
            self._stream = None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self):
        SCK.SCShareableContent.getShareableContentWithCompletionHandler_(
            self._on_content)
        # Keep the run loop alive so callbacks keep arriving
        rl = NSRunLoop.currentRunLoop()
        while self._stream is not None or not self._ready.is_set():
            rl.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))

    def _on_content(self, content, error):
        if error:
            self._error = str(error)
            self._ready.set()
            return

        displays = content.displays()
        if not displays:
            self._error = "No display found"
            self._ready.set()
            return

        filt = SCK.SCContentFilter.alloc().initWithDisplay_excludingWindows_(
            displays[0], [])

        cfg = SCK.SCStreamConfiguration.alloc().init()
        cfg.setCapturesAudio_(True)
        cfg.setExcludesCurrentProcessAudio_(True)   # don't capture ourselves
        cfg.setSampleRate_(44100)
        cfg.setChannelCount_(1)
        # Video required by the API — keep it minimal
        cfg.setWidth_(2)
        cfg.setHeight_(2)

        self._output = _Output.alloc().init()
        self._output.configure(self._push)

        self._stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(
            filt, cfg, None)

        # Serial queue for audio callbacks
        q = _libdispatch.dispatch_queue_create(b'cymatic.audio', None)
        q_ptr = ctypes.c_void_p(q)

        ok = self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self._output, _SCStreamOutputType_Audio, q_ptr, None)

        self._stream.startCaptureWithCompletionHandler_(self._on_started)

    def _on_started(self, error):
        if error:
            self._error = str(error)
            self._stream = None
        self._ready.set()


def is_available() -> bool:
    """True if ScreenCaptureKit is importable (macOS 12.3+)."""
    try:
        import ScreenCaptureKit  # noqa
        return True
    except ImportError:
        return False
