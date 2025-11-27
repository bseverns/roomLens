#!/usr/bin/env python3
"""
Plot Axis — quick-and-dirty stream visualizer
--------------------------------------------

Subscribe to serial, OSC, stdin, or a saved NDJSON file and watch both the raw
sensor values and the normalized features produced by the mapping. Uses
``plotext`` for terminal plots by default with a matplotlib fallback when you
want a windowed dashboard.

Example sessions
~~~~~~~~~~~~~~~~
- Serial rig + default mapping:
    python tools/plotaxis.py --serial-port /dev/ttyACM0 --mapping config/mapping.default.yaml

- OSC stream only (axes rendered, raw suppressed):
    python tools/plotaxis.py --osc-port 9000 --backend matplotlib

- File replay (bad-room stress case shipped in ``data/``):
    python tools/plotaxis.py --file data/bad_room.ndjson --loop
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, Mapping, MutableMapping, Optional, Tuple

# Repo-local helpers
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from roomlens.mapping import clamp01, _resolve_feature_value, _resolve_transform
from roomlens import MappingPipeline
from tools.capture_logger import iter_json_lines, iter_osc_payloads, iter_serial_json


def load_mapping(path: Path) -> Mapping[str, object]:
    return MappingPipeline.from_yaml(path).mapping


def compute_feature_vectors(
    frame: Mapping[str, object], mapping: Mapping[str, object]
) -> Tuple[Dict[str, float], Dict[str, float]]:
    raw: Dict[str, float] = {}
    normalized: Dict[str, float] = {}
    for sensor_name, sensor_cfg in mapping.get("sensors", {}).items():
        if not isinstance(sensor_cfg, Mapping) or not sensor_cfg.get("enabled", False):
            continue
        for feature_name, feature_cfg in sensor_cfg.get("features", {}).items():
            if not isinstance(feature_cfg, Mapping):
                continue
            raw_value = _resolve_feature_value(sensor_name, feature_name, feature_cfg, frame)
            transform = _resolve_transform(feature_cfg)
            try:
                normalized_value = clamp01(transform(raw_value))
            except Exception:
                normalized_value = float("nan")
            key = f"{sensor_name}.{feature_name}"
            raw[key] = raw_value
            normalized[key] = normalized_value
    return raw, normalized


def iter_frames_from_file(path: Path, loop: bool) -> Iterator[Dict[str, object]]:
    while True:
        with path.open("r", encoding="utf-8") as handle:
            for frame in iter_json_lines(handle):
                yield frame
        if not loop:
            break


# ---------------------------------------------------------------------------
# Plotting backends
# ---------------------------------------------------------------------------
MATPLOTLIB_STATE: Dict[str, object] = {}


def plot_with_plotext(
    raw_hist: Mapping[str, list[float]],
    norm_hist: Mapping[str, list[float]],
    axes_hist: Mapping[str, list[float]],
    window: int,
) -> bool:
    try:
        import plotext as plt
    except Exception:
        return False

    plt.clt()
    plt.clp()
    plt.subplots(3, 1)

    plt.subplot(3, 1, 1)
    plt.title("Raw features")
    for name in sorted(raw_hist.keys())[:6]:
        plt.plot(raw_hist[name][-window:], label=name)
    plt.legend(True)

    plt.subplot(3, 1, 2)
    plt.title("Normalized features")
    for name in sorted(norm_hist.keys())[:6]:
        plt.plot(norm_hist[name][-window:], label=name)
    plt.ylim(0, 1)
    plt.legend(True)

    plt.subplot(3, 1, 3)
    plt.title("Axes")
    for name in sorted(axes_hist.keys())[:6]:
        plt.plot(axes_hist[name][-window:], label=name)
    plt.legend(True)

    plt.show()
    return True


def plot_with_matplotlib(
    raw_hist: Mapping[str, list[float]],
    norm_hist: Mapping[str, list[float]],
    axes_hist: Mapping[str, list[float]],
    window: int,
) -> bool:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return False

    if not MATPLOTLIB_STATE:
        fig, axs = plt.subplots(3, 1, figsize=(10, 9))
        plt.ion()
        MATPLOTLIB_STATE["fig"] = fig
        MATPLOTLIB_STATE["axs"] = axs
    fig = MATPLOTLIB_STATE["fig"]
    axs = MATPLOTLIB_STATE["axs"]

    for ax, title, hist in (
        (axs[0], "Raw", raw_hist),
        (axs[1], "Normalized", norm_hist),
        (axs[2], "Axes", axes_hist),
    ):
        ax.clear()
        ax.set_title(title)
        series = sorted(hist.keys())[:6]
        for name in series:
            ax.plot(hist[name][-window:], label=name)
        ax.legend(loc="upper right")
        if title == "Normalized":
            ax.set_ylim(-0.05, 1.05)
    fig.tight_layout()
    fig.canvas.draw()
    fig.canvas.flush_events()
    return True


# ---------------------------------------------------------------------------
# CLI + main loop
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot raw + normalized Room Lens streams")
    parser.add_argument("--mapping", default=str(ROOT / "config/mapping.default.yaml"))
    parser.add_argument("--serial-port", help="Live serial port (overrides stdin)")
    parser.add_argument("--serial-baud", type=int, default=115200)
    parser.add_argument("--osc-port", type=int, default=0, help="Listen for OSC frames")
    parser.add_argument("--osc-address", default="/roomlens")
    parser.add_argument("--file", help="NDJSON file to replay instead of live streams")
    parser.add_argument("--loop", action="store_true", help="Loop file playback")
    parser.add_argument("--backend", choices=["plotext", "matplotlib"], default="plotext")
    parser.add_argument("--window", type=int, default=180, help="History window (frames)")
    parser.add_argument("--refresh", type=float, default=0.35, help="Seconds between redraws")
    return parser


def frame_iterator(args: argparse.Namespace) -> Iterator[Dict[str, object]]:
    if args.file:
        return iter_frames_from_file(Path(args.file), args.loop)
    if args.serial_port:
        return iter_serial_json(args.serial_port, args.serial_baud)
    if args.osc_port:
        return iter_osc_payloads(args.osc_port, args.osc_address)
    return iter_json_lines(sys.stdin)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    mapping_path = Path(args.mapping)
    if not mapping_path.exists():
        parser.error(f"Mapping not found: {mapping_path}")

    mapping = load_mapping(mapping_path)
    pipeline = MappingPipeline(mapping)

    frames = frame_iterator(args)

    raw_hist: MutableMapping[str, list[float]] = defaultdict(list)
    norm_hist: MutableMapping[str, list[float]] = defaultdict(list)
    axes_hist: MutableMapping[str, list[float]] = defaultdict(list)

    last_render = 0.0
    try:
        for frame in frames:
            raw, norm = compute_feature_vectors(frame, mapping)
            payload = pipeline.process_frame(frame)
            axes = payload.get("axes", {}) or {}
            issues = payload.get("issues") or []

            for name, value in raw.items():
                raw_hist[name].append(value)
            for name, value in norm.items():
                norm_hist[name].append(value)
            for name, value in axes.items():
                axes_hist[name].append(value)

            for hist in (raw_hist, norm_hist, axes_hist):
                for key, series in hist.items():
                    if len(series) > args.window * 2:
                        hist[key] = series[-args.window :]

            if issues:
                for issue in issues:
                    sensor = issue.get("sensor")
                    feature = issue.get("feature")
                    print(
                        f"# issue {sensor}.{feature}: {issue.get('type')} — {issue.get('detail')}",
                        file=sys.stderr,
                    )

            now = time.time()
            if now - last_render >= args.refresh:
                last_render = now
                if args.backend == "plotext":
                    plotted = plot_with_plotext(raw_hist, norm_hist, axes_hist, args.window)
                    if not plotted:
                        print("# plotext not available; switching to matplotlib", file=sys.stderr)
                        args.backend = "matplotlib"
                if args.backend == "matplotlib":
                    plotted = plot_with_matplotlib(raw_hist, norm_hist, axes_hist, args.window)
                    if not plotted:
                        print("# matplotlib missing; printing latest frame", file=sys.stderr)
                        print(json.dumps(payload, indent=2))
    except KeyboardInterrupt:
        print("\n# Plotter stopped", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover - UI tool
    raise SystemExit(main())
