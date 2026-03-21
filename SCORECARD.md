# Penta Dragon DX — Verification Scorecard v4.2.6

## 99.7% match (598/600 checks pass)

| Field | Match | Status |
|-------|-------|--------|
| boss, form, gameplay, powerup, room, stage | 100% | OK |
| OAM0_X, OAM0_Y | 100% | OK |
| SCX | 96% | OK |
| SCY | 96% | OK |
| LCDC | 0% | structural |

**8 at 100%. Only 2 mismatches remain (intro timing — structural ceiling).**

## 15 bugs found (all invisible to manual testing)

1. Auto-scroll wrong
2. D-pad horizontal scroll wrong
3. Free Sara movement wrong
4. Invuln blink wrong (sprite hide vs palette flash)
5. Room values wrong
6. uint8 timer overflow (390 wrapped to 134)
7. Room cycling pattern wrong
8. Room interval wrong
9. SCX initial delay missing
10. Sara visible during transition
11. No vertical scroll
12. SCX not updating on room change
13. stage_changed not cleared on bonus
14. Enemy projectile visible during transition
15. Screen shake not in OG (SCY artifact)

## 9 verification tools

| Tool | Purpose |
|------|---------|
| run_comparison.sh | One-command dual-ROM runner |
| diff_report.py | Visual bar-chart scorecard |
| regression_test.py | CI threshold checker |
| timeline.py | Temporal divergence view |
| summary.py | One-line CI output |
| lua/state_dumper.lua | Memory state capture |
| lua/memory_scanner.lua | Address auto-discovery |
| lua/input_recorder.lua | Human play recording |
| lua/sprite_counter.lua | OAM visibility tracking |
