"""Output backends for Room Lens host routing.

This module centralizes everything that turns axis payloads into synth-facing
messages. Think of it as the stagehand who knows which patch bay to hit:

* **VCV Rack** – drop ``examples/vcv-rack/roomlens_scene_receiver.vcv`` or
  ``examples/vcv-rack/roomlens_texture_memory.vcv`` into your Rack inbox,
  point an OSC output at ``127.0.0.1:57120``, and patch the "Room Lens Axes"
  module straight into your scene.
* **SuperCollider** – boot ``host/supercollider/RoomLens.scd``. It listens on
  ``57120`` for ``/roomlens`` messages and already maps axes to LagControls.
* **Pure Data** – open ``patches/puredata/roomlens.pd``. It matches the
  SuperCollider mapping: the patch already routes ``/roomlens`` pairs into Pd
  receivers and a tiny grain synth you can cannibalize.

The vibe is half studio notebook, half teaching aide: you can peek at each
backend, borrow the bits you need, and keep routing tweaks versioned in git.
"""

from __future__ import annotations

import sys
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, Mapping, MutableMapping, Tuple

try:  # pragma: no cover - optional dependency for classrooms
    from pythonosc import udp_client
except Exception:  # pragma: no cover - import guard
    udp_client = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency for classrooms
    import mido
except Exception:  # pragma: no cover - import guard
    mido = None  # type: ignore[assignment]


def _flatten_axes(payload: Mapping[str, Any]) -> list[Any]:
    axes = payload.get("axes", {}) or {}
    args: list[Any] = []
    for axis, value in sorted(axes.items()):
        args.extend([axis, float(value)])
    return args


class BaseOutput(ABC):
    """Minimal interface for Room Lens outputs."""

    name: str

    def __hash__(self) -> int:  # pragma: no cover - identity semantics
        return id(self)

    @abstractmethod
    def send_axes(self, payload: Mapping[str, Any]) -> bool:
        """Best-effort emit of the given axis payload."""

    @abstractmethod
    def ping(self) -> Tuple[bool, Dict[str, str]]:
        """Check reachability and return an identity/version hint."""


@dataclass
class OscOutput(BaseOutput):
    """UDP OSC sender aimed at a synth patch inbox."""

    port: int
    host: str = "127.0.0.1"
    address: str = "/roomlens"
    name: str = field(default="osc", init=False)
    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if udp_client is not None:
            try:
                self._client = udp_client.SimpleUDPClient(self.host, self.port)
            except Exception:
                self._client = None

    def send_axes(self, payload: Mapping[str, Any]) -> bool:
        if self._client is None:
            return False
        args = _flatten_axes(payload)
        if not args:
            return True
        try:
            self._client.send_message(self.address, args)
            return True
        except Exception:
            return False

    def ping(self) -> Tuple[bool, Dict[str, str]]:
        if self._client is None:
            return False, {}
        try:
            self._client.send_message(f"{self.address}/ping", [time.time()])
            return True, {
                "id": f"osc@{self.host}:{self.port}",
                "version": "osc/udp",
            }
        except Exception:
            return False, {}


@dataclass
class MidiOutput(BaseOutput):
    """Control Change fan-out over MIDI."""

    port_name: str
    channel: int = 0
    name: str = field(default="midi", init=False)
    _port: Any = field(default=None, init=False, repr=False)
    _axis_to_cc: Dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if mido is not None:
            try:
                self._port = mido.open_output(self.port_name)
            except Exception:
                self._port = None

    def _value_to_cc(self, value: Any) -> int:
        try:
            val = float(value)
        except Exception:
            val = 0.0
        if val < 0.0:
            return 0
        if val > 1.0:
            return 127
        return int(round(val * 127))

    def send_axes(self, payload: Mapping[str, Any]) -> bool:
        if self._port is None or mido is None:
            return False
        axes = payload.get("axes", {}) or {}
        if not axes:
            return True
        try:
            for axis, value in sorted(axes.items()):
                cc = self._axis_to_cc.setdefault(axis, len(self._axis_to_cc))
                msg = mido.Message(
                    "control_change",
                    channel=self.channel,
                    control=cc,
                    value=self._value_to_cc(value),
                )
                self._port.send(msg)
            return True
        except Exception:
            return False

    def ping(self) -> Tuple[bool, Dict[str, str]]:
        if self._port is None or mido is None:
            return False, {}
        return True, {
            "id": f"midi:{self.port_name}",
            "version": f"mido/{getattr(mido, '__version__', 'unknown')}",
        }


@dataclass
class DummyOutput(BaseOutput):
    """Fallback that just echoes payloads."""

    stream: Any = sys.stdout
    name: str = field(default="stdout", init=False)

    def send_axes(self, payload: Mapping[str, Any]) -> bool:
        print(payload, file=self.stream)
        return True

    def ping(self) -> Tuple[bool, Dict[str, str]]:
        return True, {"id": "stdout", "version": "debug"}


class OutputFanout:
    """Fan out axis payloads to multiple outputs with back-pressure."""

    def __init__(self, outputs: Iterable[BaseOutput], *, max_queue: int = 64) -> None:
        self.outputs = list(outputs)
        self._max_queue = max_queue
        self._buffers: MutableMapping[int, Deque[Mapping[str, Any]]] = {
            hash(out): deque(maxlen=max_queue) for out in self.outputs
        }

    def ping_targets(self) -> None:
        for out in self.outputs:
            ok, info = out.ping()
            if ok:
                ident = info.get("id", out.name)
                version = info.get("version") or "?"
                print(f"# {out.name} online → {ident} (v={version})", file=sys.stderr)
            else:
                print(
                    f"# {out.name} offline; will buffer axes until it wakes up",
                    file=sys.stderr,
                )

    def _buffer_for(self, out: BaseOutput) -> Deque[Mapping[str, Any]]:
        return self._buffers.setdefault(hash(out), deque(maxlen=self._max_queue))

    def broadcast(self, payload: Mapping[str, Any]) -> bool:
        delivered = False
        for out in self.outputs:
            buf = self._buffer_for(out)
            sent = out.send_axes(payload)
            if sent:
                delivered = True
                while buf:
                    queued = buf.popleft()
                    if not out.send_axes(queued):
                        buf.appendleft(queued)
                        break
            else:
                if len(buf) == buf.maxlen:
                    buf.popleft()
                    print(
                        f"# dropping stale axes for {out.name}; receiver still offline",
                        file=sys.stderr,
                    )
                buf.append(payload)
        return delivered


def parse_output_spec(spec: Any, *, osc_address: str = "/roomlens") -> BaseOutput:
    """Instantiate a :class:`BaseOutput` from a YAML-friendly spec."""

    if isinstance(spec, str):
        if ":" not in spec:
            raise ValueError(f"Output '{spec}' must use 'kind:value' syntax")
        kind, value = spec.split(":", 1)
    elif isinstance(spec, Mapping) and len(spec) == 1:
        kind, value = next(iter(spec.items()))
    else:
        raise ValueError(f"Unsupported output spec: {spec!r}")

    kind = str(kind).strip().lower()

    if kind == "osc":
        host = "127.0.0.1"
        port_str = str(value)
        if isinstance(value, str) and ":" in value:
            host, port_str = value.rsplit(":", 1)
        return OscOutput(port=int(port_str), host=host, address=osc_address)
    if kind == "midi":
        return MidiOutput(port_name=str(value))
    if kind == "stdout":
        return DummyOutput()
    raise ValueError(f"Unknown output kind '{kind}' in spec {spec!r}")
