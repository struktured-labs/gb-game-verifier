#!/usr/bin/env python3
"""
Summary tool — one-line status for quick CI checks.
Prints: PASS/FAIL, match rate, field count, worst field.

Usage: python3 summary.py og.csv rm.csv [--threshold 90]
"""
import csv
import sys


def main():
    threshold = 90
    exclude = {"LCDC", "room"}

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    for i, a in enumerate(sys.argv[1:], 1):
        if a == "--threshold" and i < len(sys.argv) - 1:
            threshold = int(sys.argv[i + 1])

    if len(args) < 2:
        print("Usage: summary.py og.csv rm.csv")
        sys.exit(1)

    og = list(csv.DictReader(open(args[0])))
    rm = list(csv.DictReader(open(args[1])))
    total = min(len(og), len(rm))

    if total == 0:
        print("FAIL: no data")
        sys.exit(2)

    fields = [f for f in og[0].keys() if f != "frame" and f not in exclude]
    matches = {}
    for f in fields:
        matches[f] = sum(1 for i in range(total) if og[i].get(f) == rm[i].get(f))

    avg = sum(100 * m // total for m in matches.values()) // len(matches) if matches else 0
    perfect = sum(1 for m in matches.values() if m == total)
    worst_f = min(matches, key=matches.get) if matches else "?"
    worst_pct = 100 * matches.get(worst_f, 0) // total if matches else 0

    passed = all(100 * m // total >= threshold for m in matches.values())
    status = "PASS" if passed else "FAIL"

    print(f"{status} | {avg}% avg | {perfect}/{len(matches)} perfect | worst: {worst_f} {worst_pct}% | {total} frames")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
