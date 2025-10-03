"""Room Lens processing toolkit.

This package collects the core data-flow pieces that glue the firmware,
hosts, and teaching utilities together. It intentionally reads like a
studio notebook: verbose comments, citations inline, and obvious seams for
your own experiments.

The primary entry points are:

- :class:`roomlens.pipeline.MappingPipeline` – a reusable sensor→axes bridge
  that mirrors the behaviour of ``host/python/app.py``.
- :func:`roomlens.mapping.load_mapping` – parse the YAML mapping file shared
  across the repo.
- :func:`roomlens.demo.demo_frame` – deterministic fake sensor frames for
  rehearsals without hardware attached.

Each module is self-contained and plain Python so it can be imported by the
CLI host, the data capture tools, or any notebook you spin up in class.
"""

from .demo import demo_frame
from .mapping import (
    SensorProcessor,
    apply_mapping,
    clamp01,
    lerp,
    load_mapping,
    validate_mapping_axes,
)
from .pipeline import MappingPipeline

__all__ = [
    "apply_mapping",
    "clamp01",
    "demo_frame",
    "MappingPipeline",
    "lerp",
    "load_mapping",
    "SensorProcessor",
    "validate_mapping_axes",
]
