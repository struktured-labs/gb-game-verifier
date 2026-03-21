# GB Game Verifier

General-purpose Game Boy game verification framework. Compare original ROMs against remakes/mods frame-by-frame with memory state diffing.

**Proven results:** Found 13 bugs invisible to manual testing, drove match rate from 0% to 99.7% on Penta Dragon DX Remake.

## Quick Start

```bash
# One-command comparison (handles everything)
./run_comparison.sh "original.gb" "remake.gbc"

# Or with custom duration/interval
./run_comparison.sh "original.gb" "remake.gbc" 3600 30
```

Output:
```
  room         [####################] 100% (60/60) OK
  gameplay     [####################] 100% (60/60) OK
  SCX          [###################.]  96% (58/60) OK
  LCDC         [....................]   0% (0/60) BAD
Summary: 10 OK, 0 WARN, 1 BAD — Average: 90%
```

## Tools (8)

| Tool | Purpose | Usage |
|------|---------|-------|
| `run_comparison.sh` | One-command dual-ROM runner | `./run_comparison.sh og.gb rm.gbc` |
| `diff_report.py` | Visual bar-chart scorecard | `python3 diff_report.py og.csv rm.csv` |
| `regression_test.py` | CI-ready pass/fail checker | `python3 regression_test.py og.csv rm.csv --threshold 90` |
| `timeline.py` | Shows WHERE divergence occurs | `python3 timeline.py og.csv rm.csv` |
| `summary.py` | One-line CI output | `python3 summary.py og.csv rm.csv` |
| `lua/state_dumper.lua` | mGBA state + screenshot capture | `mgba-qt rom.gbc --script lua/state_dumper.lua` |
| `lua/memory_scanner.lua` | Auto-discover active addresses | `mgba-qt rom.gbc --script lua/memory_scanner.lua` |
| `lua/input_recorder.lua` | Record human play for replay | `mgba-qt rom.gbc --script lua/input_recorder.lua` |

## How It Works

1. **State Dumper** (Lua) runs inside mGBA, reads memory addresses every N frames, writes CSV
2. **Comparison Engine** (Python) diffs two CSVs field-by-field
3. **Reports** show match percentages, timelines, first-divergence points

```
Timeline output:
  SCX  .....XX..................................................... 96%
  room ............................................................ 100%
  OAM  ............................................................ 100%
```

## Setting Up a New Game

1. Run the **memory scanner** on the original ROM to discover active addresses:
   ```bash
   mgba-qt original.gb --script lua/memory_scanner.lua
   cat tmp/memory_scan.txt
   ```

2. Create a game config in `configs/`:
   ```yaml
   name: "My Game"
   addresses:
     - {addr: 0xFF43, name: "SCX", critical: true}
     - {addr: 0xFFBD, name: "room"}
   ```

3. Run comparison with recorded or scripted inputs

## Regression Testing (CI Integration)

```bash
# In your Makefile:
verify: all
    @bash path/to/run_comparison.sh "original.gb" "remake.gbc"
    @python3 path/to/regression_test.py tmp/verify_og/state.csv tmp/verify_rm/state.csv --threshold 90
```

The regression test exits 0 (pass) or 1 (fail), suitable for CI pipelines.

## Bugs Found on Penta Dragon (13 total)

Every single one invisible to 60+ commits of manual screenshot testing:

1. Auto-scroll wrong — OG doesn't auto-scroll
2. D-pad scroll wrong — OG doesn't scroll horizontally
3. Free Sara movement wrong — Sara fixed at (80,80)
4. Invuln blink wrong — palette flash, not sprite hide
5. Room values wrong — {5,3} not {1,5}
6. uint8 timer overflow — 390 wrapped to 134
7. Room cycling wrong — changes once then stays
8. Room interval wrong — 150 vs 390
9. SCX delay missing — OG delays 180 frames
10. Sara visible during transition — OG hides 180 frames
11. No vertical scroll — OG scrolls SCY with D-pad
12. SCX not updating on room change
13. stage_changed flag not cleared on bonus

## Requirements

- mGBA (with Lua scripting support)
- Python 3.11+
- Xvfb (for headless testing)

## License

MIT
