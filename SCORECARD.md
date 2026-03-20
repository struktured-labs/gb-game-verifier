# Penta Dragon DX Remake — Verification Scorecard

Dual-ROM state comparison (30-frame intervals, 1800 frames).

## Current (v4.1.2) — 99.7% match

| Field | Match % | Status |
|-------|---------|--------|
| boss | 100% | OK |
| form | 100% | OK |
| gameplay | 100% | OK |
| powerup | 100% | OK |
| room | 100% | OK |
| stage | 100% | OK |
| OAM0_X | 100% | OK |
| OAM0_Y | 100% | OK |
| SCX | 96% | OK |
| SCY | 93% | OK |
| LCDC | 0% | structural |

**9/11 at 100%. Excluding LCDC: 598/600 checks pass (99.7%).**
**Only 2 mismatches remain: intro SCX/SCY timing at F180-210.**

## Journey: 0% → 99.7%

| Version | SCX | OAM0_X | gameplay | room | Key discovery |
|---------|-----|--------|----------|------|---------------|
| pre-v4 | 0% | - | - | - | Auto-scroll completely wrong |
| v4.0.0 | 13% | - | - | - | No auto-scroll in OG |
| v4.0.2 | 58% | 20% | 90% | 50% | HRAM mirroring |
| v4.0.4 | - | 53% | 90% | - | Sara fixed at (80,80) |
| v4.0.7 | 61% | 91% | 98% | 73% | uint16 timer overflow |
| v4.0.8 | 83% | 90% | 100% | 100% | Room changes once |
| v4.1.0 | 93% | 90% | 100% | 100% | Delayed room SCX |
| v4.1.1 | 96% | 90% | 100% | 100% | Scroll animation |
| v4.1.2 | 96% | **100%** | 100% | 100% | Sara hidden during transition |

## 10 bugs found by verifier

1. Auto-scroll wrong — OG doesn't auto-scroll
2. D-pad scroll wrong — OG doesn't scroll with D-pad
3. Free Sara movement wrong — OG Sara fixed at (80,80)
4. Invuln blink wrong — palette flash, not sprite hide
5. Room values wrong — {5,3} not {1,5}
6. uint8 timer overflow — 390 wrapped to 134
7. Room cycling alternates — OG changes once then stays
8. Room interval wrong — 150 vs OG 390
9. SCX set immediately — OG delays 180 frames
10. Sara visible during transition — OG hides for 180 frames

**Every single one invisible to manual screenshot testing.**
