
#!/usr/bin/env python3
"""
Generate docs/MAPPING_TABLE.md from config/mapping.default.yaml
"""
import yaml
from pathlib import Path

root = Path(__file__).parents[1]
mapping_path = root / "config" / "mapping.default.yaml"
out_path = root / "docs" / "MAPPING_TABLE.md"

m = yaml.safe_load(open(mapping_path))
lines = []
lines.append("# MAPPING TABLE (human‑readable)\n")
lines.append("> Source features are normalized to 0–1. Curves are linear unless noted.\n\n")
lines.append("| Sensor | Feature | Transform | Timbre Axis | Target Range | Notes |\n")
lines.append("|---|---|---|---|---|---|\n")

def rng(v):
    if isinstance(v, list):
        return f"{v[0]} → {v[1]}"
    return str(v)

for sensor, S in m.get("sensors", {}).items():
    feats = S.get("features", {})
    for feat, F in feats.items():
        mp = F.get("map_to", {})
        lines.append("| {s} | {f} | {tr} | {ax} | {rg} | {nt} |\n".format(
            s=sensor, f=feat, tr=F.get("transform", F.get("source", "")),
            ax=mp.get("axis",""), rg=rng(mp.get("range","")), nt=F.get("notes","")
        ))

out_path.write_text("".join(lines))
print(f"Wrote {out_path}")
