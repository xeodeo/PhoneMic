"""Audio processing: volume scaling, noise gate."""
import struct
from typing import Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def scale_volume(data: bytes, factor: float) -> bytes:
    """Scale PCM-16LE audio by factor (0.0 - 1.0+)."""
    if factor >= 1.0:
        return data
    n = len(data) // 2
    if n == 0:
        return data
    samples = struct.unpack_from(f"<{n}h", data)
    scaled = [max(-32768, min(32767, int(s * factor))) for s in samples]
    return struct.pack(f"<{n}h", *scaled)


def noise_gate(data: bytes, threshold: float = 0.02) -> bytes:
    """Return silence if RMS amplitude (0-1) is below threshold."""
    if len(data) < 2:
        return data
    if _HAS_NUMPY:
        try:
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(samples ** 2))) / 32768.0
        except Exception:
            return data
    else:
        n = len(data) // 2
        samples_raw = struct.unpack_from(f"<{n}h", data)
        rms = (sum(s * s for s in samples_raw) / max(n, 1)) ** 0.5 / 32768.0
    return data if rms >= threshold else b"\x00" * len(data)
