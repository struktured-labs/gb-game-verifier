# Penta Dragon DX — Verification Scorecard v4.1.5

## Game-visible state match (excluding structural fields)

| Test | Duration | Inputs | Match Rate |
|------|----------|--------|------------|
| Idle | 30s | Start game only | **96%** (9 fields) |
| Combat | 60s | Dodge+shoot | **93%** (9 fields) |

### Field breakdown

| Field | Idle 30s | Combat 60s | Notes |
|-------|----------|------------|-------|
| boss | 100% | 100% | |
| form | 100% | 100% | |
| gameplay | 100% | 100% | |
| powerup | 100% | 100% | |
| stage | 100% | 100% | |
| OAM0_X | 100% | 100% | Sara fixed at (80,80) |
| OAM0_Y | 100% | 100% | |
| SCX | 48% | **98%** | Intro timing offset (idle), near-perfect (combat) |
| SCY | **93%** | 43% | No combat inputs (idle), scroll rate mismatch (combat) |

### Structural fields (not game-visible)

| Field | Notes |
|-------|-------|
| room (FFBD) | OG dual-buffer tilemap toggle — internal implementation |
| LCDC | GBDK tile addressing mode difference |

## 11 bugs found by verifier

Every one invisible to manual screenshot testing:
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
