#!/usr/bin/env python3
"""
Regression test — fails if match rate drops below threshold.

Usage:
    python3 regression_test.py og_state.csv rm_state.csv [--threshold 95]

Exit codes:
    0 = pass (all fields above threshold)
    1 = regression detected
    2 = insufficient data
"""
import csv
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="GB Verifier Regression Test")
    parser.add_argument("og", help="Original state CSV")
    parser.add_argument("rm", help="Remake state CSV")
    parser.add_argument("--threshold", type=int, default=90, help="Min match %% per field")
    parser.add_argument("--exclude", nargs="*", default=["LCDC", "room"],
                        help="Fields to exclude from threshold check")
    args = parser.parse_args()

    og = list(csv.DictReader(open(args.og)))
    rm = list(csv.DictReader(open(args.rm)))
    total = min(len(og), len(rm))

    if total < 10:
        print(f"FAIL: insufficient data ({total} frames)")
        sys.exit(2)

    fields = [f for f in og[0].keys() if f != "frame"]
    matches = {f: 0 for f in fields}
    for i in range(total):
        for f in fields:
            if og[i].get(f) == rm[i].get(f):
                matches[f] += 1

    regressions = []
    for f in fields:
        if f in args.exclude:
            continue
        pct = 100 * matches[f] // total
        if pct < args.threshold:
            regressions.append((f, pct))

    # Report
    checked = [f for f in fields if f not in args.exclude]
    avg = sum(100 * matches[f] // total for f in checked) // len(checked) if checked else 0

    print(f"GB VERIFIER REGRESSION TEST — {total} frames, threshold {args.threshold}%")
    print(f"Average (excl {','.join(args.exclude)}): {avg}%")
    print()

    for f in sorted(fields, key=lambda x: -matches[x]):
        pct = 100 * matches[f] // total
        excluded = " (excluded)" if f in args.exclude else ""
        status = "PASS" if pct >= args.threshold or f in args.exclude else "REGRESSION"
        print(f"  {f:12s}: {pct:3d}% {'PASS' if status == 'PASS' else '** REGRESSION **'}{excluded}")

    if regressions:
        print(f"\nFAILED: {len(regressions)} field(s) below {args.threshold}%:")
        for f, pct in regressions:
            print(f"  {f}: {pct}% (need {args.threshold}%)")
        sys.exit(1)
    else:
        print(f"\nPASSED: all checked fields at {args.threshold}%+")
        sys.exit(0)


if __name__ == "__main__":
    main()
