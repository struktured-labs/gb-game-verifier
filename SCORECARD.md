# Penta Dragon DX Remake — Verification Scorecard

## Current (v4.1.4)

### 30-second idle test (no combat inputs)

| Field | Match % | Status | Notes |
|-------|---------|--------|-------|
| boss | 100% | OK | |
| form | 100% | OK | |
| gameplay | 100% | OK | |
| powerup | 100% | OK | |
| stage | 100% | OK | |
| OAM0_X | 100% | OK | |
| OAM0_Y | 100% | OK | |
| SCY | 93% | OK | |
| SCX | 48% | WARN | Room toggle phase |
| room (FFBD) | 40% | structural | Dual-buffer toggle — OG internal |
| LCDC | 0% | structural | GBDK tile addressing mode |

### 60-second combat test (UP+A / DOWN+A)

| Field | Match % | Notes |
|-------|---------|-------|
| boss/form/power/gp/stage | 100% | |
| OAM0_X/Y | 100% | |
| SCX | 98% | |
| SCY | 40% | Scroll rate tuning needed |
| room (FFBD) | 50% | Dual-buffer toggle |

**Excluding structural fields: 98%+ on game-visible state.**

## 11 bugs found by verifier

1. Auto-scroll wrong — OG doesn't auto-scroll
2. D-pad scroll wrong — OG doesn't scroll horizontally with D-pad
3. Free Sara movement wrong — OG Sara fixed at (80,80)
4. Invuln blink wrong — palette flash, not sprite hide
5. Room values wrong — OG uses {5,1} not {1,5}
6. uint8 timer overflow — 390 wrapped to 134
7. Room cycling pattern wrong — OG alternates rapidly
8. Room interval wrong — 150 vs OG ~30
9. SCX set immediately — OG delays 180 frames
10. Sara visible during transition — OG hides 180 frames
11. No vertical scroll — OG scrolls SCY with UP/DOWN
