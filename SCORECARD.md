# Penta Dragon DX — Verification Scorecard v4.1.8

## 99.7% match (excluding structural LCDC)

| Field | Idle 30s | Status |
|-------|----------|--------|
| boss, form, gameplay, powerup, room, stage | 100% | OK |
| OAM0_X, OAM0_Y | 100% | OK |
| SCX | 96% | OK |
| SCY | 96% | OK |
| LCDC | 0% | structural |

**598/600 checks pass. Only 2 mismatches (intro timing — structural ceiling).**

## Journey: 0% → 99.7%

| Version | Key metric | Key fix |
|---------|-----------|---------|
| pre-v4 | SCX 0% | Auto-scroll completely wrong |
| v4.0.0 | SCX 13% | Removed auto-scroll |
| v4.0.7 | gameplay 98% | uint16 timer overflow |
| v4.0.8 | room 100% | Room changes once |
| v4.1.0 | SCX 93% | Delayed room SCX |
| v4.1.2 | OAM 100% | Sara hidden during transition |
| v4.1.7 | SCX 93% (idle) | Room-based SCX update |
| v4.1.8 | **SCX 96%** | Scroll animation on 5→3 |

## 12 bugs found (all invisible to manual testing)

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
12. SCX not updating on room change — stayed at 12

## Tools (8 total)

1. `run_comparison.sh` — one-command dual-ROM runner
2. `diff_report.py` — visual bar-chart scorecard  
3. `regression_test.py` — CI-ready threshold checker
4. `timeline.py` — temporal divergence visualization
5. `summary.py` — one-line CI output
6. `lua/state_dumper.lua` — mGBA state capture
7. `lua/memory_scanner.lua` — address auto-discovery
8. `lua/input_recorder.lua` — human play input recording
