# Penta Dragon DX — Verification Scorecard v4.1.7

## Idle test (30s, no combat): 99.3% match (excl LCDC)

| Field | Match | Status |
|-------|-------|--------|
| boss, form, gameplay, powerup, room, stage, OAM0_X, OAM0_Y | 100% | OK |
| SCY | 96% | OK |
| SCX | 93% | OK |
| LCDC | 0% | structural |

**10/11 at OK. 8 at 100%. Only 4 mismatches in 600 checks.**

## Combat test (60s, dodge+shoot): 93% game-visible

| Field | Match | Notes |
|-------|-------|-------|
| boss, form, gameplay, power, stage, OAM0_X, OAM0_Y | 100% | |
| SCX | 98% | |
| SCY | 43% | Scroll rate tuning |
| room | 22% | Structural (dual-buffer toggle) |

## 12 bugs found by verifier

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
12. SCX not updating on room transition
