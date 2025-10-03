
#!/usr/bin/env python3
"""Generate ``docs/MAPPING_TABLE.md`` from the shared mapping YAML."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from roomlens import load_mapping

root = Path(__file__).parents[1]
mapping_path = root / "config" / "mapping.default.yaml"
out_path = root / "docs" / "MAPPING_TABLE.md"

m = load_mapping(mapping_path)
axes_meta = m.get("axes", {})
lines = []
lines.append("# MAPPING TABLE (human‑readable)\n")
lines.append("> Source features are normalized to 0–1. Curves are linear unless noted.\n\n")
lines.append("| Sensor | Feature | Transform | Timbre Axis | Target Range | Notes |\n")
lines.append("|---|---|---|---|---|---|\n")

def format_transform(feature_cfg: dict) -> str:
    if feature_cfg.get("doc_transform"):
        return feature_cfg["doc_transform"]
    pieces = []
    if feature_cfg.get("transform"):
        pieces.append(feature_cfg["transform"].replace("_", " "))
    if feature_cfg.get("normalize"):
        if feature_cfg["normalize"] == "site":
            pieces.append("z-norm per site")
        else:
            pieces.append(f"normalize({feature_cfg['normalize']})")
    if feature_cfg.get("bandpass"):
        lo, hi = feature_cfg["bandpass"]
        pieces.append(f"band-pass {lo}–{hi} Hz")
    if feature_cfg.get("smooth_ms"):
        pieces.append(f"smooth({feature_cfg['smooth_ms']}ms)")
    if feature_cfg.get("debounce_ms"):
        pieces.append(f"debounce {feature_cfg['debounce_ms']}ms")
    if feature_cfg.get("cap"):
        pieces.append(f"cap @{feature_cfg['cap']}")
    if not pieces and feature_cfg.get("source"):
        pieces.append(feature_cfg["source"])
    return ", ".join(pieces) if pieces else "—"

def format_range(range_value, axis_info: dict, map_to: dict) -> str:
    if map_to.get("doc_range"):
        return map_to["doc_range"]
    if isinstance(range_value, list) and len(range_value) == 2:
        lo, hi = range_value
        unit = axis_info.get("doc_unit", axis_info.get("unit", ""))
        suffix = f" {unit}" if unit else ""
        return f"{lo} → {hi}{suffix}"
    return str(range_value)

for sensor_key, sensor_cfg in m.get("sensors", {}).items():
    sensor_label = sensor_cfg.get("label", sensor_key.replace("_", " ").title())
    for feature_key, feature_cfg in sensor_cfg.get("features", {}).items():
        feature_label = feature_cfg.get("label", feature_key.replace("_", " ").title())
        map_to = feature_cfg.get("map_to", {})
        axis_key = map_to.get("axis", "")
        axis_info = axes_meta.get(axis_key, {})
        axis_label = axis_info.get("label", axis_key.replace("_", " ").title())
        target_range = format_range(map_to.get("range", ""), axis_info, map_to)
        notes = feature_cfg.get("notes", axis_info.get("desc", ""))
        lines.append(
            "| {sensor} | {feature} | {transform} | {axis} | {target} | {notes} |\n".format(
                sensor=sensor_label,
                feature=feature_label,
                transform=format_transform(feature_cfg),
                axis=axis_label,
                target=target_range,
                notes=notes,
            )
        )

out_path.write_text("".join(lines))
print(f"Wrote {out_path}")
