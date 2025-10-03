"""Host CLI wiring tests keep the focus on argument juggling, not hardware IO."""
from __future__ import annotations

import argparse
from types import SimpleNamespace
from typing import Any, Dict

import pytest

import host.python.app as app


def make_args(**overrides: Any) -> argparse.Namespace:
    """Build a minimal argparse namespace mirroring :func:`app.main`."""

    defaults: Dict[str, Any] = {
        "mapping": "mapping.yaml",
        "osc": 0,
        "demo": False,
        "port": "auto",
        "baud": 115200,
        "dry_audio": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def stubbed_pipeline(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Replace heavy mapping helpers with lightweight doubles."""

    captured: Dict[str, Any] = {"instances": []}

    def fake_load_mapping(path: app.Path) -> Dict[str, Any]:
        captured["path"] = path
        return {"axes": {"demo": 1.0}}

    class DummyPipeline:
        def __init__(self, mapping: Dict[str, Any]):
            self.mapping = mapping
            self.bound_client = None
            self.has_osc_client = False
            self.emitted = []
            captured["instances"].append(self)

        def bind_osc_client(self, client: Any) -> None:
            self.bound_client = client
            self.has_osc_client = True

        def process_frame(self, frame: Dict[str, Any]) -> Dict[str, Any]:
            return {"frame": frame}

        def emit_osc(self, payload: Dict[str, Any]) -> bool:
            self.emitted.append(payload)
            return True

    monkeypatch.setattr(app, "load_mapping", fake_load_mapping)
    monkeypatch.setattr(app, "MappingPipeline", DummyPipeline)
    return captured


def test_frame_iterator_uses_demo_when_serial_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """If pyserial is absent the CLI should fall back to demo frames."""

    monkeypatch.setattr(app, "serial", None)

    def fake_demo_frames():
        yield "demo"

    monkeypatch.setattr(app, "demo_frames", fake_demo_frames)

    frames = app.frame_iterator(make_args())
    assert next(frames) == "demo"


def test_frame_iterator_uses_demo_when_no_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty USB roster should also land on the demo generator."""

    monkeypatch.setattr(app, "serial", object())
    monkeypatch.setattr(app, "find_serial", lambda: None)

    demo_calls = {"count": 0}

    def fake_demo_frames():
        demo_calls["count"] += 1
        yield "fallback"

    monkeypatch.setattr(app, "demo_frames", fake_demo_frames)

    frames = app.frame_iterator(make_args())
    assert next(frames) == "fallback"
    assert demo_calls["count"] == 1


def test_frame_iterator_prefers_serial_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once a port shows up the iterator should lean on hardware frames."""

    monkeypatch.setattr(app, "serial", object())
    monkeypatch.setattr(app, "find_serial", lambda: "/dev/ttyACM0")

    serial_calls: Dict[str, Any] = {}

    def fake_serial_frames(port: str, baud: int):
        serial_calls["args"] = (port, baud)
        yield {"source": "serial"}

    monkeypatch.setattr(app, "serial_frames", fake_serial_frames)

    frames = app.frame_iterator(make_args())
    assert next(frames) == {"source": "serial"}
    assert serial_calls["args"] == ("/dev/ttyACM0", 115200)


def test_setup_pipeline_binds_osc_when_requested(
    monkeypatch: pytest.MonkeyPatch, stubbed_pipeline: Dict[str, Any]
) -> None:
    """OSC opt-in should build a UDP client and mark the pipeline ready."""

    created_clients = []

    class DummyClient:
        def __init__(self, host: str, port: int) -> None:
            self.host = host
            self.port = port

    def fake_simple_udp_client(host: str, port: int) -> DummyClient:
        client = DummyClient(host, port)
        created_clients.append(client)
        return client

    monkeypatch.setattr(
        app, "udp_client", SimpleNamespace(SimpleUDPClient=fake_simple_udp_client)
    )

    args = make_args(osc=9000)
    pipeline = app.setup_pipeline(args)

    assert stubbed_pipeline["path"].name == "mapping.yaml"
    assert pipeline.has_osc_client is True
    assert pipeline.bound_client.host == "127.0.0.1"
    assert pipeline.bound_client.port == 9000
    assert len(created_clients) == 1


def test_setup_pipeline_skips_osc_when_disabled(
    monkeypatch: pytest.MonkeyPatch, stubbed_pipeline: Dict[str, Any]
) -> None:
    """No flag, no OSC client—keep things classroom-friendly."""

    calls = []

    def fake_simple_udp_client(host: str, port: int) -> None:
        calls.append((host, port))
        raise AssertionError("SimpleUDPClient should not be constructed")

    monkeypatch.setattr(
        app, "udp_client", SimpleNamespace(SimpleUDPClient=fake_simple_udp_client)
    )

    pipeline = app.setup_pipeline(make_args())

    assert pipeline.has_osc_client is False
    assert calls == []
