# Penta Dragon DX Remake — Verification Scorecard

Dual-ROM state comparison (30-frame intervals, 1800 frames).

## Current (v4.1.0)

| Field | Match % | Status | Notes |
|-------|---------|--------|-------|
| boss | 100% | OK | |
| form | 100% | OK | |
| gameplay | 100% | OK | F540 exact match |
| powerup | 100% | OK | |
| room | 100% | OK | Single transition 5→3 |
| stage | 100% | OK | |
| SCX | 93% | OK | 4 mismatches from room scroll animation |
| SCY | 93% | OK | |
| OAM0_X | 90% | OK | |
| OAM0_Y | 90% | OK | |
| LCDC | 0% | structural | GBDK tile addressing mode |

**7 at 100%. 10/11 at 90%+. Average (excl LCDC): 97%**

## Journey from 0% to 97%

| Version | SCX | gameplay | OAM0_X | room | Key discovery |
|---------|-----|----------|--------|------|---------------|
| pre-v4 | 0% | - | - | - | Auto-scroll was completely wrong |
| v4.0.0 | 13% | - | - | - | Removed auto-scroll |
| v4.0.2 | 58% | 90% | 20% | 50% | HRAM mirroring |
| v4.0.4 | - | 90% | 53% | - | Sara fixed at center |
| v4.0.7 | 61% | **98%** | **91%** | 73% | uint16 timer overflow (!!) |
| v4.0.8 | 83% | **100%** | 90% | **100%** | Room changes once |
| v4.1.0 | **93%** | **100%** | 90% | **100%** | Delayed room SCX (180 frames) |

## 9 bugs found (invisible to manual testing)

1. Auto-scroll wrong — OG SCX fixed, no auto-scroll
2. D-pad scroll wrong — OG doesn't scroll with D-pad  
3. Free Sara movement wrong — OG Sara fixed at OAM (80,80)
4. Invuln blink wrong — OG palette flash, not sprite hide
5. Room values wrong — {5,3} not {1,5}
6. uint8 timer overflow — 390 wrapped to 134 silently
7. Room cycling alternates — OG changes once then stays
8. Room interval wrong — 150 frames vs OG 390
9. SCX set immediately — OG delays 180 frames after gameplay start
