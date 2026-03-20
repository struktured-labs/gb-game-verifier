# Penta Dragon DX Remake — Verification Scorecard

Tracked via dual-ROM state comparison (30-frame intervals, 1800 frames).

## Current (v4.0.7)

| Field | Match % | Status | Notes |
|-------|---------|--------|-------|
| boss | 100% | OK | |
| form | 100% | OK | |
| powerup | 100% | OK | |
| stage | 100% | OK | |
| gameplay | 98% | OK | F570 vs F540 (30 frame gap) |
| OAM0_X | 91% | OK | Sara fixed at (80,80) |
| OAM0_Y | 91% | OK | Invuln palette flash not hide |
| SCY | 90% | OK | |
| room | 73% | WARN | 30-frame offset from intro timing |
| SCX | 61% | WARN | Room-based, timing dependent |
| LCDC | 0% | structural | GBDK tile addressing mode |

**8/11 fields at 88%+. 5 at 100%. Average (excl LCDC): 86%**

## History

| Version | gameplay | OAM0_X | OAM0_Y | SCX | room | Key fix |
|---------|----------|--------|--------|-----|------|---------|
| pre-v4 | - | - | - | 0% | - | Auto-scroll completely wrong |
| v4.0.0 | - | - | - | 13% | - | Removed auto-scroll |
| v4.0.2 | 90% | 20% | 56% | 58% | 50% | HRAM mirroring |
| v4.0.4 | 90% | 53% | 53% | - | - | Sara fixed at center |
| v4.0.6 | 91% | 81% | 81% | 48% | 53% | Invuln blink, OAM clear |
| v4.0.7 | **98%** | **91%** | **91%** | **61%** | **73%** | uint16 timer overflow fix |

## Bugs found by verifier (impossible to find via screenshots)

1. **Auto-scroll wrong** — OG SCX fixed, no auto-scroll
2. **D-pad scroll wrong** — OG doesn't scroll with D-pad
3. **Free Sara movement wrong** — OG Sara fixed at OAM (80,80)
4. **Invuln blink wrong** — OG keeps sprite at (80,80), palette flash
5. **Room values wrong** — OG uses rooms {5,3} not {1,5}
6. **uint8 timer overflow** — 390 wrapped to 134 silently (!!!)
7. **Room cycling too fast** — 150 frames vs OG 390
