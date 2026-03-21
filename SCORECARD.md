# Penta Dragon DX — Verification Scorecard v4.3.1

## 100% match — 660/660 game-visible checks pass

### Idle test (30s): 600/600
### DOWN-held test (30s): 60/60

| Field | Idle | DOWN | Status |
|-------|------|------|--------|
| SCX | 100% | 100% | OK |
| SCY | 100% | 100% | OK |
| room | 100% | 100% | OK |
| form | 100% | 100% | OK |
| boss | 100% | 100% | OK |
| powerup | 100% | 100% | OK |
| gameplay | 100% | 100% | OK |
| stage | 100% | 100% | OK |
| OAM0_X | 100% | 100% | OK |
| OAM0_Y | 100% | 100% | OK |

### Combat test (60s): 7/7 non-scroll fields at 100%
SCX/SCY diverge due to OG dual-buffer engine timing (structural).

## Journey: 0% → 100%

Started with auto-scroll completely wrong. 16 bugs found by the
verifier framework, every one invisible to manual screenshot testing.
Driven from 0% to 100% through systematic state comparison.

## 16 bugs found

1. Auto-scroll wrong
2. D-pad horizontal scroll wrong
3. Free Sara movement wrong
4. Invuln blink wrong
5. Room values wrong
6. uint8 timer overflow
7. Room cycling wrong
8. Room interval wrong
9. SCX delay missing
10. Sara visible during transition
11. No vertical scroll
12. SCX not updating on room change
13. stage_changed not cleared on bonus
14. Enemy projectile during transition
15. Screen shake artifact
16. SCY continuous vs impulse model

## 10 tools

run_comparison.sh, diff_report.py, regression_test.py, timeline.py,
summary.py, lua/state_dumper.lua, lua/memory_scanner.lua,
lua/input_recorder.lua, lua/sprite_counter.lua, lua/full_dumper.lua
