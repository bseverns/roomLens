
#!/usr/bin/env python3
"""
Capture Logger (opt-in)

Reads JSON frames (stdin or serial soon) and writes to CSV/Parquet
AFTER explicit confirmation. Use for short study captures.

Usage:
  python tools/capture_logger.py --file data/capture.csv
"""
import argparse, csv, json, sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    args = ap.parse_args()

    out = Path(args.file)
    print("This tool saves sensor frames to disk.")
    ans = input(f"Save to {out}? Type YES to proceed: ").strip()
    if ans != "YES":
        print("Aborting without saving.")
        return

    out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = None
    with open(out, "w", newline="") as f:
        writer = None
        for line in sys.stdin:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if fieldnames is None:
                fieldnames = list(row.keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            writer.writerow(row)
            f.flush()

if __name__ == "__main__":
    main()
