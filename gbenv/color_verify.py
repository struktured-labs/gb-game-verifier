"""
Stage 5: Colorization Verification — explores visual states to catch palette/color gaps.

For DMG→CGB romhacks/remakes, verifies that:
1. All BG tiles have appropriate CGB palette assignments
2. Sprite palettes match intended color schemes
3. Palette changes occur at correct game events (boss fights, powerups, etc.)
4. No visual glitches (wrong palette on tiles, missing colors, etc.)

Approaches:
A. Tile-palette coverage: ensure every tile_id maps to a non-default palette
B. State-triggered palettes: verify boss/powerup palette changes fire correctly
C. Screen comparison: visual diff between OG (DMG greens) and remake (CGB colors)
D. Palette register sniffing: dump BCPS/BCPD/OCPS/OCPD during gameplay
"""
import json
import csv
import numpy as np
from pathlib import Path
from typing import Optional


def generate_palette_dumper_lua(output_path: str, frames: int = 600,
                                 sample_interval: int = 4) -> str:
    """Generate Lua to dump CGB palette registers during gameplay."""
    return f"""-- CGB Palette Register Dumper
-- Dumps BG and OBJ palette data every {sample_interval} frames
local frame_count = 0
local done = false
local f = io.open("{output_path}", "w")
f:write("frame,LCDC,SCX,SCY,BGP,OBP0,OBP1,WX,WY")
-- CGB palette data: 8 BG palettes × 4 colors × 2 bytes = 64 bytes
for i = 0, 7 do
    f:write(",BG" .. i .. "_0,BG" .. i .. "_1,BG" .. i .. "_2,BG" .. i .. "_3")
end
for i = 0, 7 do
    f:write(",OBJ" .. i .. "_0,OBJ" .. i .. "_1,OBJ" .. i .. "_2,OBJ" .. i .. "_3")
end
f:write("\\n")

function read_cgb_palette(is_obj)
    local spec_reg = is_obj and 0xFF6A or 0xFF68
    local data_reg = is_obj and 0xFF6B or 0xFF69
    local colors = {{}}
    for pal = 0, 7 do
        local pal_colors = {{}}
        for col = 0, 3 do
            local idx = pal * 8 + col * 2
            -- Set index (auto-increment)
            emu:write8(spec_reg, idx + 0x80)
            local lo = emu:read8(data_reg)
            emu:write8(spec_reg, idx + 1 + 0x80)
            local hi = emu:read8(data_reg)
            local bgr555 = lo + hi * 256
            table.insert(pal_colors, bgr555)
        end
        table.insert(colors, pal_colors)
    end
    return colors
end

function on_frame()
    if done then return end
    frame_count = frame_count + 1

    if frame_count % {sample_interval} == 0 then
        local row = tostring(frame_count)
        -- LCD registers
        row = row .. "," .. emu:read8(0xFF40)  -- LCDC
        row = row .. "," .. emu:read8(0xFF43)  -- SCX
        row = row .. "," .. emu:read8(0xFF42)  -- SCY
        row = row .. "," .. emu:read8(0xFF47)  -- BGP
        row = row .. "," .. emu:read8(0xFF48)  -- OBP0
        row = row .. "," .. emu:read8(0xFF49)  -- OBP1
        row = row .. "," .. emu:read8(0xFF4B)  -- WX
        row = row .. "," .. emu:read8(0xFF4A)  -- WY

        -- CGB BG palettes
        local bg_pals = read_cgb_palette(false)
        for _, pal in ipairs(bg_pals) do
            for _, col in ipairs(pal) do
                row = row .. "," .. col
            end
        end

        -- CGB OBJ palettes
        local obj_pals = read_cgb_palette(true)
        for _, pal in ipairs(obj_pals) do
            for _, col in ipairs(pal) do
                row = row .. "," .. col
            end
        end

        f:write(row .. "\\n")
    end

    if frame_count >= {frames} then
        done = true
        f:close()
        print("Palette dump done: " .. frame_count .. " frames")
    end
end

callbacks:add("frame", on_frame)
print("CGB palette dumper started — {frames} frames")
"""


def generate_tile_palette_map_lua(output_path: str) -> str:
    """Generate Lua to dump the BG tile→palette attribute map from VRAM."""
    return f"""-- BG Tile Palette Map Dumper
-- Reads VRAM bank 1 attribute map for tile→palette assignments
-- Must be run on CGB ROM

-- Wait for gameplay
local frame_count = 0
local done = false

function dump_attributes()
    -- Read BG attribute map from VRAM bank 1
    -- Switch to VRAM bank 1
    emu:write8(0xFF4F, 1)

    local f = io.open("{output_path}", "w")
    f:write("tilemap_addr,tile_x,tile_y,attr_byte,palette,vram_bank,x_flip,y_flip,priority\\n")

    -- Tilemap 0 (0x9800-0x9BFF = 32×32 tiles)
    for ty = 0, 31 do
        for tx = 0, 31 do
            local addr = 0x9800 + ty * 32 + tx
            local attr = emu:read8(addr)
            local pal = attr % 8
            local vbank = math.floor(attr / 8) % 2
            local xflip = math.floor(attr / 32) % 2
            local yflip = math.floor(attr / 64) % 2
            local prio = math.floor(attr / 128)
            f:write(string.format("0x%04X,%d,%d,0x%02X,%d,%d,%d,%d,%d\\n",
                    addr, tx, ty, attr, pal, vbank, xflip, yflip, prio))
        end
    end

    -- Switch back to VRAM bank 0
    emu:write8(0xFF4F, 0)

    -- Also dump tile IDs from bank 0
    local f2 = io.open("{output_path}.tiles", "w")
    f2:write("tilemap_addr,tile_x,tile_y,tile_id\\n")
    for ty = 0, 31 do
        for tx = 0, 31 do
            local addr = 0x9800 + ty * 32 + tx
            local tile_id = emu:read8(addr)
            f2:write(string.format("0x%04X,%d,%d,0x%02X\\n", addr, tx, ty, tile_id))
        end
    end
    f2:close()

    f:close()
    print("Tile palette map dumped")
end

function on_frame()
    if done then return end
    frame_count = frame_count + 1
    -- Wait for gameplay (FFC1=1)
    if emu:read8(0xFFC1) == 1 and frame_count > 100 then
        dump_attributes()
        done = true
    end
    if frame_count > 2000 then
        done = true
        print("Timeout — FFC1 never reached 1")
    end
end

callbacks:add("frame", on_frame)
print("Waiting for gameplay to dump tile palette map...")
"""


def generate_sprite_palette_checker_lua(output_path: str, frames: int = 600) -> str:
    """Generate Lua to check sprite palette assignments during gameplay."""
    return f"""-- Sprite Palette Checker
-- Dumps OAM data with palette assignments during gameplay
local frame_count = 0
local done = false
local f = io.open("{output_path}", "w")
f:write("frame,slot,y,x,tile,flags,palette,x_flip,y_flip,priority,cgb_pal\\n")

function on_frame()
    if done then return end
    frame_count = frame_count + 1

    -- Only dump when in gameplay
    if emu:read8(0xFFC1) ~= 1 then return end

    -- Every 30 frames, dump all visible sprites
    if frame_count % 30 == 0 then
        for slot = 0, 39 do
            local base = 0xFE00 + slot * 4
            local y = emu:read8(base)
            local x = emu:read8(base + 1)
            local tile = emu:read8(base + 2)
            local flags = emu:read8(base + 3)

            -- Skip hidden sprites
            if y > 0 and y < 160 and x > 0 and x < 168 then
                local pal = math.floor(flags / 16) % 2  -- DMG palette
                local xflip = math.floor(flags / 32) % 2
                local yflip = math.floor(flags / 64) % 2
                local prio = math.floor(flags / 128)
                local cgb_pal = flags % 8  -- CGB palette

                f:write(string.format("%d,%d,%d,%d,0x%02X,0x%02X,%d,%d,%d,%d,%d\\n",
                        frame_count, slot, y, x, tile, flags, pal, xflip, yflip, prio, cgb_pal))
            end
        end
    end

    if frame_count >= {frames} then
        done = true
        f:close()
        print("Sprite palette check done: " .. frame_count .. " frames")
    end
end

callbacks:add("frame", on_frame)
print("Sprite palette checker started — {frames} frames")
"""


def analyze_palette_dump(csv_path: str) -> dict:
    """Analyze a palette dump CSV for colorization issues."""
    if not Path(csv_path).exists():
        return {"error": f"File not found: {csv_path}"}

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {"error": "Empty dump"}

    # Track unique palette states
    bg_palette_states = set()
    obj_palette_states = set()
    lcd_states = set()

    for row in rows:
        lcdc = row.get("LCDC", "0")
        lcd_states.add(lcdc)

        # Collect BG palette colors
        for i in range(8):
            key = f"BG{i}_0"
            if key in row:
                colors = tuple(int(row.get(f"BG{i}_{c}", 0)) for c in range(4))
                bg_palette_states.add((i, colors))

        # Collect OBJ palette colors
        for i in range(8):
            key = f"OBJ{i}_0"
            if key in row:
                colors = tuple(int(row.get(f"OBJ{i}_{c}", 0)) for c in range(4))
                obj_palette_states.add((i, colors))

    # Check for issues
    issues = []

    # Issue 1: All-zero palettes (missing color assignment)
    for pal_idx, colors in bg_palette_states:
        if all(c == 0 for c in colors):
            issues.append({
                "type": "zero_palette",
                "palette_type": "BG",
                "index": pal_idx,
                "severity": "warning",
                "message": f"BG palette {pal_idx} is all black (0,0,0,0)",
            })

    for pal_idx, colors in obj_palette_states:
        if all(c == 0 for c in colors):
            issues.append({
                "type": "zero_palette",
                "palette_type": "OBJ",
                "index": pal_idx,
                "severity": "warning",
                "message": f"OBJ palette {pal_idx} is all black (0,0,0,0)",
            })

    # Issue 2: Duplicate palettes (wasted palette slot)
    bg_colors_list = [(idx, colors) for idx, colors in bg_palette_states]
    for i, (idx1, c1) in enumerate(bg_colors_list):
        for j, (idx2, c2) in enumerate(bg_colors_list):
            if i < j and c1 == c2 and idx1 != idx2:
                issues.append({
                    "type": "duplicate_palette",
                    "palette_type": "BG",
                    "indices": [idx1, idx2],
                    "severity": "info",
                    "message": f"BG palettes {idx1} and {idx2} are identical",
                })

    return {
        "total_frames": len(rows),
        "unique_bg_palette_states": len(bg_palette_states),
        "unique_obj_palette_states": len(obj_palette_states),
        "lcd_states": list(lcd_states),
        "issues": issues,
        "bg_palettes": [
            {"index": idx, "colors": list(colors)}
            for idx, colors in sorted(bg_palette_states)
        ],
        "obj_palettes": [
            {"index": idx, "colors": list(colors)}
            for idx, colors in sorted(obj_palette_states)
        ],
    }


def analyze_tile_palette_map(attr_csv: str, tile_csv: str) -> dict:
    """Analyze tile→palette mapping for coverage gaps."""
    if not Path(attr_csv).exists():
        return {"error": f"File not found: {attr_csv}"}

    with open(attr_csv) as f:
        attrs = list(csv.DictReader(f))

    tiles_data = []
    if Path(tile_csv).exists():
        with open(tile_csv) as f:
            tiles_data = list(csv.DictReader(f))

    # Build tile_id → palette mapping
    tile_to_palette = {}
    palette_usage = {i: 0 for i in range(8)}

    for i, attr in enumerate(attrs):
        pal = int(attr.get("palette", 0))
        palette_usage[pal] += 1

        if i < len(tiles_data):
            tile_id = int(tiles_data[i].get("tile_id", "0"), 16)
            if tile_id not in tile_to_palette:
                tile_to_palette[tile_id] = set()
            tile_to_palette[tile_id].add(pal)

    # Check for issues
    issues = []

    # Tiles using only palette 0 (might be default/unassigned)
    default_only = [
        tid for tid, pals in tile_to_palette.items()
        if pals == {0} and tid != 0
    ]
    if len(default_only) > 10:
        issues.append({
            "type": "many_default_palette",
            "count": len(default_only),
            "severity": "warning",
            "message": f"{len(default_only)} non-empty tiles only use palette 0 (may be uncolored)",
        })

    # Tiles assigned to multiple palettes (dynamic assignment)
    multi_pal = {
        tid: list(pals) for tid, pals in tile_to_palette.items()
        if len(pals) > 1
    }

    return {
        "total_tiles_mapped": len(attrs),
        "unique_tile_ids": len(tile_to_palette),
        "palette_usage": palette_usage,
        "multi_palette_tiles": len(multi_pal),
        "default_only_tiles": len(default_only),
        "issues": issues,
    }


def analyze_sprite_palettes(csv_path: str) -> dict:
    """Analyze sprite palette assignments for correctness."""
    if not Path(csv_path).exists():
        return {"error": f"File not found: {csv_path}"}

    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return {"error": "Empty sprite dump"}

    # Map tile ranges to expected palettes (from CLAUDE.md)
    EXPECTED_SPRITE_PALETTES = {
        (0x00, 0x1F): 0,  # Effects/projectiles
        (0x20, 0x27): 2,  # Sara Witch
        (0x28, 0x2F): 1,  # Sara Dragon
        (0x30, 0x3F): 3,  # Crows
        (0x40, 0x4F): 4,  # Hornets
        (0x50, 0x5F): 5,  # Orcs
        (0x60, 0x6F): 6,  # Humanoids
        (0x70, 0x7F): 7,  # Special (catfish)
    }

    correct = 0
    wrong = 0
    issues = []

    for row in rows:
        tile = int(row.get("tile", "0"), 16)
        cgb_pal = int(row.get("cgb_pal", 0))

        expected = None
        for (lo, hi), pal in EXPECTED_SPRITE_PALETTES.items():
            if lo <= tile <= hi:
                expected = pal
                break

        if expected is not None:
            if cgb_pal == expected:
                correct += 1
            else:
                wrong += 1
                if len(issues) < 20:
                    issues.append({
                        "frame": int(row.get("frame", 0)),
                        "slot": int(row.get("slot", 0)),
                        "tile": f"0x{tile:02X}",
                        "expected_palette": expected,
                        "actual_palette": cgb_pal,
                    })

    total = correct + wrong
    accuracy = correct / total if total > 0 else 0

    return {
        "total_sprites_checked": total,
        "correct_palette": correct,
        "wrong_palette": wrong,
        "accuracy": accuracy,
        "issues": issues[:10],
    }


if __name__ == "__main__":
    # Generate all verification Lua scripts
    output_dir = Path("../pipeline_output")
    output_dir.mkdir(exist_ok=True)

    print("=== Generating Stage 5 Lua Scripts ===")

    # Palette dumper
    lua = generate_palette_dumper_lua("palette_dump.csv", frames=1200)
    (output_dir / "palette_dumper.lua").write_text(lua)
    print(f"  Palette dumper: {output_dir / 'palette_dumper.lua'}")

    # Tile palette map
    lua = generate_tile_palette_map_lua("tile_palette_map.csv")
    (output_dir / "tile_palette_map.lua").write_text(lua)
    print(f"  Tile palette map: {output_dir / 'tile_palette_map.lua'}")

    # Sprite palette checker
    lua = generate_sprite_palette_checker_lua("sprite_palettes.csv", frames=1200)
    (output_dir / "sprite_palette_checker.lua").write_text(lua)
    print(f"  Sprite palette checker: {output_dir / 'sprite_palette_checker.lua'}")

    print("\nRun with:")
    print("  mgba-qt -l pipeline_output/palette_dumper.lua rom.gbc")
    print("  mgba-qt -l pipeline_output/tile_palette_map.lua rom.gbc")
    print("  mgba-qt -l pipeline_output/sprite_palette_checker.lua rom.gbc")
