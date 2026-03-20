# Penta Dragon DX Remake — Verification Scorecard

Tracked via dual-ROM state comparison (30-frame intervals, 1800 frames).

## Current (v4.0.3)

| Field | Match % | Status | Notes |
|-------|---------|--------|-------|
| boss | 100% | OK | |
| form | 100% | OK | |
| powerup | 100% | OK | |
| stage | 100% | OK | |
| SCY | 90% | OK | Title screen offset (8 vs 0) |
| gameplay | 88% | OK | HRAM mirroring working |
| room | 51% | WARN | Room timing differs from OG |
| SCX | 44% | BAD | Room-based SCX + timing lag |
| OAM0_Y | 51% | WARN | Sara Y position differs |
| OAM0_X | 23% | BAD | Sara X position differs |
| LCDC | 0% | BAD | Tile addressing mode (0x8000 vs 0x8800) |

## History

| Version | SCX | SCY | gameplay | room | Notes |
|---------|-----|-----|----------|------|-------|
| pre-verifier | 0% | 0% | - | - | Auto-scroll completely wrong |
| v4.0.0 | 13% | 6% | - | - | Removed auto-scroll |
| v4.0.1 | 58% | 90% | 28% | 28% | Fixed title SCX, SCY tracking |
| v4.0.2 | 58% | 90% | 90% | 50% | HRAM mirroring, room values |
| v4.0.3 | 44% | 90% | 88% | 51% | Room-based SCX (timing issues) |

## How to reproduce

```bash
# Generate input sequence
cat > tmp/verify_inputs.csv << 'EOF'
130,128
133,0
150,1
153,0
500,1
503,0
700,1
703,0
900,17
1200,17
1500,17
EOF

# Run OG
DISPLAY=:97 mgba-qt original.gb --script lua/state_dumper.lua

# Run Remake
DISPLAY=:97 mgba-qt remake.gbc --script lua/state_dumper.lua

# Compare
python3 compare.py --og tmp/verify_og --remake tmp/verify_rm
```
