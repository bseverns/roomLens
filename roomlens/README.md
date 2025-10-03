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
