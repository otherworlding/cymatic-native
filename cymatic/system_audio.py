"""
System audio routing via BlackHole virtual audio driver.

BlackHole creates a loopback device so audio from Apple Music, Spotify,
browsers, etc. flows into the visualizer while still playing through speakers.

Install once:  https://existential.audio/products/blackhole/
Setup:         Run setup_guide() to open step-by-step instructions.
"""

import subprocess

try:
    import sounddevice as sd
    _SD_OK = True
except ImportError:
    _SD_OK = False


def find_blackhole():
    """Return (device_index, name) of first BlackHole input device, or None.
    Forces a PortAudio device list refresh so newly installed drivers are found."""
    if not _SD_OK:
        return None
    try:
        # Re-initialise PortAudio so macOS CoreAudio changes are picked up
        sd._terminate()
        sd._initialize()
        for i, d in enumerate(sd.query_devices()):
            if d['max_input_channels'] > 0 and 'blackhole' in d['name'].lower():
                return (i, d['name'])
    except Exception:
        pass
    return None


def is_available():
    """True if BlackHole is already installed."""
    return find_blackhole() is not None


def open_download_page():
    """Open the BlackHole download page in the default browser."""
    subprocess.Popen(['open', 'https://existential.audio/products/blackhole/'])


def open_audio_midi_setup():
    """Open Audio MIDI Setup so the user can build the Multi-Output Device."""
    subprocess.Popen(['open', '-a', 'Audio MIDI Setup'])
