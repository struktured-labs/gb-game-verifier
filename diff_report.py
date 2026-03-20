#!/usr/bin/env python3
"""Quick diff report between two state CSVs."""
import csv
import sys

def main():
    if len(sys.argv) < 3:
        print("Usage: diff_report.py og_state.csv rm_state.csv")
        sys.exit(1)

    og = list(csv.DictReader(open(sys.argv[1])))
    rm = list(csv.DictReader(open(sys.argv[2])))
    total = min(len(og), len(rm))

    if total == 0:
        print("No data to compare")
        sys.exit(1)

    fields = [f for f in og[0].keys() if f != "frame"]
    matches = {f: 0 for f in fields}

    for i in range(total):
        for f in fields:
            if og[i].get(f) == rm[i].get(f):
                matches[f] += 1

    # Scorecard
    print(f"{'='*50}")
    print(f"GB VERIFIER REPORT — {total} frames compared")
    print(f"{'='*50}")
    print()

    ok = warn = bad = 0
    for f in sorted(fields, key=lambda x: -matches[x]):
        pct = 100 * matches[f] // total
        if pct >= 80:
            s = "OK"; ok += 1
        elif pct >= 50:
            s = "WARN"; warn += 1
        else:
            s = "BAD"; bad += 1
        bar = "#" * (pct // 5) + "." * (20 - pct // 5)
        print(f"  {f:12s} [{bar}] {pct:3d}% ({matches[f]}/{total}) {s}")

    avg = sum(matches.values()) * 100 // (total * len(fields)) if fields else 0
    print()
    print(f"Summary: {ok} OK, {warn} WARN, {bad} BAD — Average: {avg}%")
    print()

    # First mismatch per field
    for f in fields:
        pct = 100 * matches[f] // total
        if pct < 100:
            for i in range(total):
                if og[i].get(f) != rm[i].get(f):
                    print(f"  First {f} mismatch: F{og[i]['frame']} OG={og[i][f]} RM={rm[i][f]}")
                    break

if __name__ == "__main__":
    main()
