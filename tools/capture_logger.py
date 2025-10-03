
#!/usr/bin/env python3
"""
Capture Logger (opt-in)

Reads JSON frames (stdin or serial soon) and writes to CSV/Parquet
AFTER explicit confirmation. Use for short study captures.

Usage:
  python tools/capture_logger.py --file data/capture.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path


def capture_stream(stdin, out_path, confirm_callback):
    """Capture JSON rows from *stdin* and persist them to *out_path* as CSV."""

    if not confirm_callback(out_path):
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = None
    with open(out_path, "w", newline="") as f:
        writer = None
        for line in stdin:
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

    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    args = ap.parse_args()

    out = Path(args.file)

    def confirm_callback(path):
        print("This tool saves sensor frames to disk.")
        ans = input(f"Save to {path}? Type YES to proceed: ").strip()
        if ans != "YES":
            print("Aborting without saving.")
            return False
        return True

    capture_stream(sys.stdin, out, confirm_callback)

if __name__ == "__main__":
    main()
