# Adding a New Game to GB Game Verifier

This guide explains how to set up verification for any Game Boy / Game Boy Color game.

## Step 1: Discover Active Addresses

Run the memory scanner on the original ROM to find which addresses change during gameplay:

```bash
mgba-qt original.gb --script lua/memory_scanner.lua
cat tmp/memory_scan.txt
```

This will output something like:
```
Changed addresses (326 total):
  0xC000: 0 -> 80 (frame 720)   # OAM sprite data
  0xFF43: 0 -> 12 (frame 720)   # SCX scroll register
  0xFFBD: 0 -> 5 (frame 720)    # Game-specific state
```

## Step 2: Create a Game Config

Create `configs/your_game.yaml`:

```yaml
name: "Your Game"
platform: "GB"  # or "GBC"

addresses:
  # Hardware registers (common to all games)
  - {addr: 0xFF43, name: "SCX", critical: true}
  - {addr: 0xFF42, name: "SCY", critical: true}
  - {addr: 0xFF40, name: "LCDC"}
  - {addr: 0xFE00, name: "OAM0_Y"}
  - {addr: 0xFE01, name: "OAM0_X"}

  # Game-specific addresses (from scanner)
  - {addr: 0xFFBD, name: "level"}
  - {addr: 0xFFBF, name: "boss_flag"}
  # ... add more based on scanner results

inputs:
  start_game:
    desc: "Navigate menu and start gameplay"
    sequence:
      - {frame: 100, keys: 0x08}  # START
      - {frame: 103, keys: 0x00}
```

## Step 3: Create Input Sequences

Record human play or create scripted inputs:

```bash
# Record from human play
mgba-qt original.gb --script lua/input_recorder.lua
# Plays are saved to tmp/recorded_inputs.csv

# Or create manual inputs
echo "100,8" > inputs.csv   # START at frame 100
echo "103,0" >> inputs.csv  # Release
```

## Step 4: Run Comparison

```bash
./run_comparison.sh "original.gb" "remake.gbc" 1800 30
```

## Step 5: Set Up Regression Testing

Add to your Makefile:
```makefile
verify: all
    @bash path/to/gb-game-verifier/run_comparison.sh \
        "original.gb" "remake.gbc" 1800 30
    @python3 path/to/gb-game-verifier/regression_test.py \
        tmp/verify_og/state.csv tmp/verify_rm/state.csv \
        --threshold 90 --exclude LCDC
```

## Tips

- **Start with hardware registers** (SCX, SCY, LCDC, OAM) — these are universal
- **Use the memory scanner** to find game-specific addresses like HP, lives, level
- **Mark structural fields** (like LCDC tile addressing mode) as excluded in regression tests
- **Run multiple scenarios** — idle, single-button, and combat inputs find different bugs
- **Check the timeline** (`timeline.py`) to see WHERE divergences occur — intro, gameplay, transitions

## Common Patterns

| Pattern | What it means |
|---------|--------------|
| SCX/SCY mismatch | Scroll timing or speed differs |
| OAM mismatch | Sprite position or visibility differs |
| LCDC always 0% | Different tile addressing mode (structural) |
| Field matches idle but not combat | Engine timing dependent behavior |
