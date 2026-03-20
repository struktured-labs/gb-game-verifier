# Penta Dragon DX Remake — Verification Scorecard

Dual-ROM state comparison (30-frame intervals, 1800 frames).

## Current (v4.0.8)

| Field | Match % | Status | Notes |
|-------|---------|--------|-------|
| boss | 100% | OK | |
| form | 100% | OK | |
| gameplay | 100% | OK | F540 exact match |
| powerup | 100% | OK | |
| room | 100% | OK | Single transition 5→3 |
| stage | 100% | OK | |
| SCY | 93% | OK | |
| OAM0_X | 90% | OK | Sara fixed at (80,80) |
| OAM0_Y | 90% | OK | Palette flash invuln blink |
| SCX | 83% | OK | Room-based, delayed transition |
| LCDC | 0% | structural | GBDK tile addressing mode |

**7/11 fields at 100%. 10/11 at 83%+. Average (excl LCDC): 93%**

## Progress

| Version | gameplay | OAM0_X | SCX | room | Key fix |
|---------|----------|--------|-----|------|---------|
| pre-v4 | - | - | 0% | - | Auto-scroll completely wrong |
| v4.0.0 | - | - | 13% | - | Removed auto-scroll |
| v4.0.2 | 90% | 20% | 58% | 50% | HRAM mirroring |
| v4.0.4 | 90% | 53% | - | - | Sara fixed at center |
| v4.0.6 | 91% | 81% | 48% | 53% | Invuln blink fix |
| v4.0.7 | **98%** | **91%** | **61%** | **73%** | uint16 timer overflow |
| v4.0.8 | **100%** | **90%** | **83%** | **100%** | Room changes once |

## 8 bugs found (invisible to manual testing)

1. Auto-scroll wrong — OG SCX fixed, no auto-scroll
2. D-pad scroll wrong — OG doesn't scroll with D-pad
3. Free Sara movement wrong — OG Sara fixed at OAM (80,80)
4. Invuln blink wrong — OG uses palette flash, not sprite hide
5. Room values wrong — OG uses rooms {5,3} not {1,5}
6. uint8 timer overflow — 390 wrapped to 134 silently
7. Room cycling alternates — OG changes once then stays
8. Room interval wrong — 150 frames vs OG 390
