# roomlens/ — shared processing core

> Think of this folder as the "studio notebook" version of the host logic. We
> broke the feature→axis plumbing out of `host/python/app.py` so every script,
> tool, or notebook in the repo can riff on the same pipeline without copy/paste
> drift.

## What's inside

| Module | Purpose | Starter moves |
| --- | --- | --- |
| `mapping.py` | Load/validate YAML mappings and turn normalized features into synth axes. | Call `load_mapping(...)`, tweak the dict, and feed frames into `apply_mapping(...)`. |
| `pipeline.py` | Thin wrapper around the mapping helpers with OSC niceties. | `MappingPipeline.from_yaml(...).process_frame(frame)` |
| `demo.py` | Drop-in fake sensor frames for rehearsal mode. | `demo_frame()` inside a loop when hardware is unplugged. |
| `__init__.py` | Convenience exports so `from roomlens import MappingPipeline` feels natural. | Import what you need and get weird with it. |

## Why centralize?

* **Interoperability**: Firmware devs, SuperCollider tweakers, and notebook nerds
  all reference the same mapping semantics. No more "wait, why does the Pd tool
  map PIR differently?" surprises.
* **Teaching**: The modules are annotated like a class handout. Students can read
  the code and see the math behind the mapping without digging through a CLI
  script.
* **Swappability**: Bring your own sensors. Add a resolver in `mapping.py` or a
  custom processor and the rest of the repo automatically respects it.

## Quick riff

```python
from pathlib import Path
from roomlens import MappingPipeline, demo_frame

pipeline = MappingPipeline.from_yaml(Path("config/mapping.default.yaml"))
frame = demo_frame()
payload = pipeline.process_frame(frame)
print(payload["axes"])  # {'grain_density': 0.15, ...}
```

Now that you're armed with the shared core, the CLI host is just one flavor of
front end. Patch it into data-loggers, Jupyter demos, or your own OSC gadgets.
Document the weird experiments. High-five the room.

### Transform hooks (aka "mapping spells")

Mapping YAML entries can declare transforms such as ``log10_clamp`` or
``inverse_exp(centers=[50, 120], k=1.2)``. The string is parsed into a safe
callable from :mod:`roomlens.mapping`, so every client shares the same math. A
quick cheatsheet:

| Transform | What it does | Tunable bits |
| --- | --- | --- |
| ``log10_clamp`` | Converts linear amplitude into decibels then remaps into ``[0, 1]``. | ``floor_db``: how deep the silence well goes (default ``-60``). |
| ``softclip(threshold=0.8, slope=4)`` | Leaves values below ``threshold`` alone and eases into the ceiling with an exponential knee. | ``threshold`` (0→1), ``slope`` (exponent ≥ 1). |
| ``inverse_exp(centers=[...], k=1.0)`` | Treats each centre as a "sweet spot" distance and ramps toward zero beyond it. Average of all centres. | ``centers`` (list of positive floats), ``k`` (falloff aggression). |

Unknown transforms explode loudly with a :class:`ValueError` so workshops catch
typos before soundcheck. Bring your own transform by inserting a callable into
the feature config or extending ``_TRANSFORM_FACTORIES`` when you publish new
spells.

Pro tip: ``source`` entries in the YAML are now honoured before the baked-in
resolvers, including the ``a|b`` syntax for "try ``a`` then fall back to ``b``".
That keeps forthcoming hardware logs (e.g. raw ``distance_cm``) and the existing
normalized demo frames in sync.
