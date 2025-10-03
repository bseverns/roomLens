"""Demo frame generators.

When the hardware is unplugged (or still on the bench), we still need frames
flowing through the mapping stack so workshops can rehearse the mapping
logic. The functions here mirror the ad-hoc demo generator that originally
lived in ``host/python/app.py`` but are factored out so any script can import
them.
"""
from __future__ import annotations

import math
import time
from typing import Dict


def demo_frame(t: float | None = None) -> Dict[str, float]:
    """Synthesize a musically-interesting fake feature frame.

    Parameters
    ----------
    t:
        Seconds elapsed since an arbitrary reference time. ``None`` defaults to
        the current ``time.time()`` delta so you can call :func:`demo_frame`
        without worrying about clock management.

    Returns
    -------
    dict
        Keys mimic the JSON exported by the Teensy skeleton firmware. Values
        sit roughly within ``[0, 1]`` so they drop straight into the mapping
        pipeline.
    """

    if t is None:
        t = time.time()

    def wob(freq: float) -> float:
        """Cheap LFO stack used to fake sensor motion for demos."""

        return 0.5 + 0.5 * math.sin(freq * t) * math.cos(0.7 * freq * t)

    return {
        "t": int(time.time() * 1000),
        "mic_rms": 0.12 + 0.1 * wob(1.7),
        "mic_sc": 0.40 + 0.3 * wob(0.9),
        "tof_motion": abs(0.5 - wob(2.3)) * 2.0,
        "tof_near": wob(0.5),
        "lux": 0.3 + 0.6 * wob(0.1),
        "flicker": wob(3.1),
        "motion": 1 if wob(2.3) > 0.65 else 0,
    }
