#!/usr/bin/env python3
"""Generate ASCII timeline showing when each field matches/diverges."""
import csv
import sys


def main():
    if len(sys.argv) < 3:
        print("Usage: timeline.py og.csv rm.csv [field1 field2 ...]")
        sys.exit(1)

    og = list(csv.DictReader(open(sys.argv[1])))
    rm = list(csv.DictReader(open(sys.argv[2])))
    total = min(len(og), len(rm))

    fields = sys.argv[3:] if len(sys.argv) > 3 else [
        f for f in og[0].keys() if f not in ("frame", "LCDC")
    ]

    # Header
    print(f"{'Field':>12s}  ", end="")
    for i in range(0, total, max(1, total // 60)):
        f = int(og[i]["frame"])
        if f % 300 == 0:
            print(f"{f//60:>2d}s", end="")
        else:
            print(" ", end="")
    print()

    # Timeline per field
    for field in fields:
        line = ""
        matches = 0
        for i in range(total):
            if og[i].get(field) == rm[i].get(field):
                line += "."
                matches += 1
            else:
                line += "X"
        pct = 100 * matches // total
        # Compress to ~60 chars
        compressed = ""
        step = max(1, total // 60)
        for i in range(0, total, step):
            chunk = line[i:i+step]
            if "X" in chunk:
                compressed += "X"
            else:
                compressed += "."
        print(f"{field:>12s}  {compressed} {pct}%")


if __name__ == "__main__":
    main()
