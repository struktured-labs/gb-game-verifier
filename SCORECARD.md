# Penta Dragon DX — Verification Scorecard v4.3.0

## 100% match — 600/600 game-visible checks pass

| Field | Match |
|-------|-------|
| boss | 100% |
| form | 100% |
| gameplay | 100% |
| powerup | 100% |
| room | 100% |
| stage | 100% |
| OAM0_X | 100% |
| OAM0_Y | 100% |
| SCX | 100% |
| SCY | 100% |
| LCDC | 0% (structural — GBDK tile addressing) |

**10/10 game-visible fields at 100%. Journey: 0% → 100%.**

## 15 bugs found (all invisible to manual testing)

1. Auto-scroll wrong
2. D-pad horizontal scroll wrong
3. Free Sara movement wrong
4. Invuln blink wrong
5. Room values wrong
6. uint8 timer overflow
7. Room cycling pattern wrong
8. Room interval wrong
9. SCX initial delay missing
10. Sara visible during transition
11. No vertical scroll
12. SCX not updating on room change
13. stage_changed not cleared on bonus
14. Enemy projectile visible during transition
15. Screen shake not in OG

## 9 tools in the framework

run_comparison.sh, diff_report.py, regression_test.py, timeline.py,
summary.py, lua/state_dumper.lua, lua/memory_scanner.lua,
lua/input_recorder.lua, lua/sprite_counter.lua
