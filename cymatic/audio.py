"""Audio capture, FFT analysis, and beat detection."""

import threading
import numpy as np
from numpy.fft import rfft
from .config import FFT_SIZE, SAMPLE_RATE

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_OK = True
except ImportError:
    AUDIO_OK = False


class AudioEngine:
    def __init__(self):
        self._fft      = np.zeros(FFT_SIZE // 2 + 1)
        self._lock     = threading.Lock()
        self._win      = np.hanning(FFT_SIZE)
        self._buf      = np.zeros(FFT_SIZE)
        self.stream    = None
        self.current_sr = SAMPLE_RATE  # updated by start_file to file's native rate

    # ── Internal ─────────────────────────────────────────────────────────────

    def _push(self, mono: np.ndarray):
        """Ingest new audio samples; compute FFT from rolling buffer."""
        n = len(mono)
        if n >= FFT_SIZE:
            self._buf = mono[-FFT_SIZE:].astype(np.float32)
        else:
            self._buf = np.roll(self._buf, -n)
            self._buf[-n:] = mono.astype(np.float32)
        fft = np.abs(rfft(self._buf * self._win))
        with self._lock:
            self._fft = fft

    def _stop_stream(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    # ── Public start methods ──────────────────────────────────────────────────

    def start_mic(self, device=None) -> bool:
        self._stop_stream()
        if not AUDIO_OK:
            return False

        def cb(indata, frames, t, status):
            try:
                mono = indata[:, 0] if indata.ndim > 1 else indata.flatten()
                self._push(mono)
            except Exception:
                pass

        try:
            self.stream = sd.InputStream(
                device=device, channels=1,
                samplerate=SAMPLE_RATE, blocksize=512,
                callback=cb,
            )
            self.stream.start()
            return True
        except Exception as e:
            print(f"Mic error: {e}")
            return False

    def start_file(self, path: str) -> bool:
        """Play an audio file through the speakers and analyse it simultaneously."""
        self._stop_stream()
        if not AUDIO_OK:
            return False

        try:
            data, sr = sf.read(path, always_2d=True, dtype='float32')
            # Play at the file's native sample rate — no resampling needed.
            # Store it so the FFT frequency axis stays correct.
            self.current_sr = sr

            pos = [0]

            def cb(outdata, frames, t, status):
                try:
                    start = pos[0]
                    end   = start + frames
                    chunk = data[start:end]

                    if len(chunk) < frames:
                        # Loop seamlessly
                        remainder = data[:max(0, frames - len(chunk))]
                        chunk     = np.vstack([chunk, remainder]) if len(chunk) else data[:frames]
                        pos[0]    = max(0, frames - (end - len(data)))
                    else:
                        pos[0] = end

                    ch = min(chunk.shape[1], outdata.shape[1])
                    n  = min(len(chunk), frames)
                    outdata[:n, :ch] = chunk[:n, :ch]
                    if ch < outdata.shape[1]:
                        outdata[:n, ch:] = 0
                    if n < frames:
                        outdata[n:] = 0

                    self._push(chunk[:n, 0])
                except Exception:
                    outdata[:] = 0

            out_ch = min(2, data.shape[1])
            self.stream = sd.OutputStream(
                channels=out_ch, samplerate=sr,
                blocksize=1024, callback=cb,
            )
            self.stream.start()
            return True
        except Exception as e:
            print(f"File error: {e}")
            return False

    def stop(self):
        self._stop_stream()

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_fft(self) -> np.ndarray:
        with self._lock:
            return self._fft.copy()

    # ── Analysis helpers ──────────────────────────────────────────────────────

    def band(self, fft: np.ndarray, lo: float, hi: float) -> float:
        n   = len(fft)
        nyq = self.current_sr / 2
        a   = max(0, int(lo / nyq * n))
        b   = min(n - 1, int(hi / nyq * n))
        if b <= a:
            return 0.0
        return float(np.mean(fft[a:b + 1])) / (FFT_SIZE / 2)

    def dominant_hz(self, fft: np.ndarray) -> float:
        n   = len(fft)
        nyq = self.current_sr / 2
        lo  = max(2, int(60 / nyq * n))
        if lo >= n:
            return 440.0
        return (lo + int(np.argmax(fft[lo:]))) * nyq / n

    def spectral_centroid(self, fft: np.ndarray) -> float:
        """Weighted average frequency — changes with every note and harmonic shift."""
        n    = len(fft)
        nyq  = self.current_sr / 2
        lo   = max(2, int(60 / nyq * n))
        hi   = min(n - 1, int(8000 / nyq * n))
        sub  = fft[lo:hi + 1]
        tot  = float(np.sum(sub))
        if tot < 1e-6:
            return 440.0
        freqs = np.linspace(lo * nyq / n, hi * nyq / n, len(sub))
        return float(np.sum(freqs * sub) / tot)

    def top_peaks(self, fft: np.ndarray, count: int = 3):
        n   = len(fft)
        nyq = self.current_sr / 2
        lo  = max(2, int(60 / nyq * n))
        mx  = FFT_SIZE / 2
        out = []
        for i in range(lo + 1, n - 1):
            v = fft[i]
            if v > fft[i - 1] and v > fft[i + 1] and v / mx > 0.04:
                out.append((i * nyq / n, float(v) / mx))
        out.sort(key=lambda x: -x[1])
        return out[:count]

    @staticmethod
    def list_devices():
        if not AUDIO_OK:
            return []
        out = []
        try:
            for i, d in enumerate(sd.query_devices()):
                if d['max_input_channels'] > 0:
                    out.append((i, d['name']))
        except Exception:
            pass
        return out
