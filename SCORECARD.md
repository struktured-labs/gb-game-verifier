# Penta Dragon DX Remake — Verification Scorecard

Tracked via dual-ROM state comparison (30-frame intervals, 1800 frames).

## Current (v4.0.6)

| Field | Match % | Status | Notes |
|-------|---------|--------|-------|
| boss | 100% | OK | |
| form | 100% | OK | |
| powerup | 100% | OK | |
| stage | 100% | OK | |
| gameplay | 91% | OK | HRAM mirroring |
| SCY | 88% | OK | |
| OAM0_X | 81% | OK | Fixed invuln blink + intro OAM clear |
| OAM0_Y | 81% | OK | Fixed invuln blink + intro OAM clear |
| room | 53% | WARN | Room transition timing differs |
| SCX | 48% | BAD | Intro timing + room SCX lag |
| LCDC | 0% | BAD | GBDK tile addressing mode (structural) |

**8/11 fields at 80%+. 5 at 100%.**

## History

| Version | SCX | SCY | gameplay | OAM0_X | OAM0_Y | room | Notes |
|---------|-----|-----|----------|--------|--------|------|-------|
| pre-verifier | 0% | 0% | - | - | - | - | Auto-scroll completely wrong |
| v4.0.0 | 13% | 6% | - | - | - | - | Removed auto-scroll |
| v4.0.1 | 58% | 90% | 28% | - | - | 28% | Fixed title SCX, removed SCY tracking |
| v4.0.2 | 58% | 90% | 90% | 20% | 56% | 50% | HRAM mirroring, room values |
| v4.0.3 | 44% | 90% | 88% | 23% | 51% | 51% | Room-based SCX |
| v4.0.4 | - | 93% | 90% | 53% | 53% | - | Fixed Sara to (72,64) |
| v4.0.5 | 48% | 88% | 91% | 55% | 55% | 53% | No D-pad scroll, room-transition SCX |
| v4.0.6 | 48% | 88% | 91% | **81%** | **81%** | 53% | Invuln palette flash, intro OAM clear |

## Key findings from verifier

1. **Auto-scroll was wrong** (v4.0.0) — OG SCX stays fixed, no auto-scroll
2. **D-pad scroll was wrong** (v4.0.5) — OG doesn't scroll with D-pad either
3. **Free Sara movement was wrong** (v4.0.4) — OG Sara fixed at OAM (80,80)
4. **Invuln blink was wrong** (v4.0.6) — OG keeps Sara at (80,80), not (0,0)
5. **Room cycling values wrong** (v4.0.2) — OG uses rooms {5,3} not {1,5}
6. **LCDC is structural** — GBDK uses different tilemap addressing, can't fix

All of these survived 60+ commits of manual screenshot testing.
