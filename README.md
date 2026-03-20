# GB Game Verifier

General-purpose Game Boy game verification framework. Compare original ROMs against remakes/mods frame-by-frame with memory state diffing.

## What it does

Runs two GB/GBC ROMs side-by-side with identical inputs, captures memory state and screenshots at regular intervals, then diffs everything and reports behavioral divergences.

**Found a critical auto-scroll bug in its first real use** — a "verified" feature that had survived 60+ commits of manual screenshot testing was proven wrong in under 2 minutes by comparing SCX register values between original and remake.

## Quick Start

```bash
# Compare two ROMs with default inputs (30 seconds, state every 60 frames)
uv run python compare.py \
  --og "path/to/original.gb" \
  --remake "path/to/remake.gbc" \
  --frames 1800 --interval 60

# Or run the Lua dumper directly in mGBA
VERIFY_DUMP_DIR=tmp/dump mgba-qt rom.gbc --script lua/state_dumper.lua
```

## Architecture

```
gb-game-verifier/
├── compare.py          # Main comparison engine (Python)
├── lua/
│   └── state_dumper.lua  # mGBA Lua script — dumps memory + screenshots
├── configs/
│   └── penta_dragon.yaml # Per-game memory address config
└── README.md
```

### State Dumper (Lua)

Runs inside mGBA via `--script`. Every N frames:
- Reads configurable memory addresses (SCX, SCY, HP, boss flags, etc.)
- Writes to CSV: `frame,keys,addr1,addr2,...`
- Takes a screenshot

### Comparison Engine (Python)

1. Runs the OG ROM with recorded inputs → dumps state
2. Runs the remake ROM with same inputs → dumps state
3. Diffs the two CSVs field-by-field
4. Optionally diffs screenshots (pixel-level with PIL/numpy)
5. Generates a divergence report with severity levels

## Memory Address Configs

Each game needs a YAML config specifying which memory addresses to track:

```yaml
# configs/penta_dragon.yaml
name: "Penta Dragon"
addresses:
  - {addr: 0xFF43, name: "SCX", critical: true}
  - {addr: 0xFF42, name: "SCY", critical: true}
  - {addr: 0xFFBD, name: "room"}
  - {addr: 0xFFBF, name: "boss_flag"}
  - {addr: 0xFFC1, name: "gameplay"}
```

## Requirements

- mGBA (with Lua scripting support)
- Python 3.11+ with `uv`
- Optional: PIL/numpy for screenshot comparison

## Roadmap

- [ ] YAML-based game configs (not hardcoded addresses)
- [ ] Input recording from human play sessions
- [ ] RL agent for automated game exploration
- [ ] Video-guided input inference (watch gameplay, replay on remake)
- [ ] Web UI for side-by-side frame comparison
- [ ] CI integration (run on PR, block if divergences increase)

## License

MIT
