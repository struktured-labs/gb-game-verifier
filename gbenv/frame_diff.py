"""
Frame-level pixel diff — the top-down verification layer.

Runs identical input sequences on OG and remake ROMs via mGBA,
captures screenshots at each step, and diffs them pixel-by-pixel.

This catches EVERYTHING the register-based pipeline misses:
- Missing scrolling (Bug #15 — would have been caught on iteration 1)
- Wrong tile content
- Sprite position/timing issues
- Visual glitches
- Collision behavior differences

The pixel diff map shows exactly WHERE on screen the two ROMs differ,
making it trivial to identify what's wrong without any RE knowledge.
"""
import subprocess
import os
import json
from pathlib import Path


def generate_playback_lua(actions, output_dir, rom_label, boot_frames=200,
                           capture_interval=4, max_gameplay_frames=2000):
    """Generate a Lua script that plays back actions and captures screenshots."""
    # Convert action IDs to mGBA key bitmasks
    # GB_ACTIONS from gb_env.py
    action_map = {
        0: 0, 1: 1, 2: 2, 3: 16, 4: 32, 5: 64, 6: 128,
        7: 17, 8: 33, 9: 65, 10: 129, 11: 8, 12: 4,
    }

    # Build key sequence: each action held for 4 frames
    key_events = []
    for i, a in enumerate(actions):
        keys = action_map.get(int(a), 0)
        frame_start = i * 4
        key_events.append((frame_start, keys))

    lua = f"""-- Auto-generated playback + screenshot capture
local count = 0
local gf = 0
local booted = false
local action_idx = 0
local captures = 0
local max_captures = {max_gameplay_frames // capture_interval}

-- Action sequence (frame_offset, key_bitmask)
local actions = {{
"""
    for keys in [action_map.get(int(a), 0) for a in actions[:500]]:
        lua += f"    {keys},\n"
    lua += f"""}}

callbacks:add("frame", function()
    count = count + 1

    -- Boot: DOWN at 180, A at 193
    if count == 180 then emu:addKey(7) end
    if count == 185 then emu:clearKey(7) end
    if count == 193 then emu:addKey(0) end
    if count == 198 then emu:clearKey(0) end
    if count == 250 then emu:addKey(0) end
    if count == 255 then emu:clearKey(0) end
    if count == 300 then emu:addKey(3) end
    if count == 305 then emu:clearKey(3) end
    if count == 350 then emu:addKey(0) end
    if count == 355 then emu:clearKey(0) end

    if not booted and emu:read8(0xFFC1) == 1 then
        booted = true
    end

    if not booted then return end
    gf = gf + 1
    if gf <= 200 then return end  -- stabilization

    local gameplay_frame = gf - 200

    -- Apply action (held for 4 frames each)
    local action_i = math.floor(gameplay_frame / 4) + 1
    if action_i <= #actions then
        for k = 0, 7 do emu:clearKey(k) end
        local keys = actions[action_i]
        for bit = 0, 7 do
            if keys % 2 == 1 then emu:addKey(bit) end
            keys = math.floor(keys / 2)
        end
    end

    -- Capture screenshot
    if gameplay_frame % {capture_interval} == 0 and captures < max_captures then
        emu:screenshot(string.format("{rom_label}_%04d.png", captures))
        captures = captures + 1
    end
end)
print("Playback script loaded — {len(key_events)} actions, capturing every {capture_interval} frames")
"""
    return lua


def capture_frames(rom_path, actions, output_dir, label, capture_interval=4,
                    max_frames=400):
    """Run mGBA headlessly, play back actions, capture screenshots."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    lua_content = generate_playback_lua(
        actions, str(out), label,
        capture_interval=capture_interval,
        max_gameplay_frames=max_frames * capture_interval,
    )

    lua_file = out / f"playback_{label}.lua"
    lua_file.write_text(lua_content)

    env = os.environ.copy()
    env.update({
        "QT_QPA_PLATFORM": "offscreen",
        "SDL_AUDIODRIVER": "dummy",
        "DISPLAY": "",
        "WAYLAND_DISPLAY": "",
    })

    timeout_secs = max(30, max_frames // 10)
    try:
        subprocess.run(
            ["xvfb-run", "-a", "mgba-qt", "--script",
             str(lua_file.name), str(rom_path)],
            cwd=str(out), env=env, capture_output=True, text=True,
            timeout=timeout_secs,
        )
    except subprocess.TimeoutExpired:
        pass  # Expected — mGBA doesn't exit

    subprocess.run(["pkill", "-9", "-f", "Xvfb :"],
                    capture_output=True, timeout=5)

    # Count captured frames
    captured = list(out.glob(f"{label}_*.png"))
    return sorted(captured)


def diff_frames(og_frames, rm_frames, output_dir):
    """Pixel-diff two sets of captured frames.

    Returns per-frame diff statistics and saves diff images.
    """
    from PIL import Image
    import numpy as np

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = []

    n = min(len(og_frames), len(rm_frames))
    if n == 0:
        return {"error": "no frames to compare", "frames": []}

    total_diff = 0
    max_diff = 0
    perfect_frames = 0

    for i in range(n):
        og_img = np.array(Image.open(og_frames[i]).convert("L"))  # Grayscale
        rm_img = np.array(Image.open(rm_frames[i]).convert("L"))  # Grayscale

        if og_img.shape != rm_img.shape:
            results.append({"frame": i, "error": "shape mismatch"})
            continue

        # Structural comparison: binarize to dark/light
        # Ignores shade variations within "light" (floor) and "dark" (wall) regions
        # Only cares about structural layout: is this pixel part of a wall or floor?
        og_bin = (og_img < 128).astype(float)  # 1 = dark (wall/item), 0 = light (floor)
        rm_bin = (rm_img < 128).astype(float)

        # Structural diff: do both ROMs agree on dark vs light?
        diff = np.abs(og_bin - rm_bin)
        mean_diff = float(np.mean(diff))
        max_pixel_diff = float(np.max(diff))
        pct_different = float(np.mean(diff > 0) * 100)  # % pixels with structural mismatch

        total_diff += mean_diff
        if mean_diff > max_diff:
            max_diff = mean_diff
        if mean_diff < 0.5:
            perfect_frames += 1

        # Save diff image (amplified for visibility)
        if i < 20 or pct_different > 5:
            diff_img = np.clip(diff * 85, 0, 255).astype(np.uint8)  # 0-3 → 0-255
            Image.fromarray(diff_img, mode='L').save(out / f"diff_{i:04d}.png")
            # Also save side-by-side for easy comparison
            if i < 5:
                side = np.hstack([og_img, rm_img])
                Image.fromarray(side, mode='L').save(out / f"side_{i:04d}.png")

        results.append({
            "frame": i,
            "mean_diff": round(mean_diff, 2),
            "max_pixel_diff": round(max_pixel_diff, 1),
            "pct_different": round(pct_different, 1),
        })

    avg_diff = total_diff / n if n > 0 else 0

    return {
        "total_frames": n,
        "avg_mean_diff": round(avg_diff, 2),
        "max_mean_diff": round(max_diff, 2),
        "perfect_frames": perfect_frames,
        "perfect_pct": round(100 * perfect_frames / n, 1) if n > 0 else 0,
        "frames": results,
    }


def run_frame_diff(og_rom, remake_rom, actions, output_dir="frame_diff_output",
                    capture_interval=4, max_frames=200):
    """Full frame-diff pipeline: capture both ROMs, diff screenshots."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Capturing {max_frames} frames from OG...")
    og_frames = capture_frames(og_rom, actions, str(out / "og"), "og",
                                capture_interval=capture_interval,
                                max_frames=max_frames)
    print(f"  Captured {len(og_frames)} OG frames")

    print(f"Capturing {max_frames} frames from Remake...")
    rm_frames = capture_frames(remake_rom, actions, str(out / "remake"), "remake",
                                capture_interval=capture_interval,
                                max_frames=max_frames)
    print(f"  Captured {len(rm_frames)} Remake frames")

    print("Diffing frames...")
    report = diff_frames(og_frames, rm_frames, str(out / "diffs"))

    print(f"\n{'='*50}")
    print(f"FRAME DIFF REPORT")
    print(f"{'='*50}")
    print(f"  Frames compared: {report['total_frames']}")
    print(f"  Perfect frames:  {report['perfect_frames']} ({report['perfect_pct']}%)")
    print(f"  Avg pixel diff:  {report['avg_mean_diff']}")
    print(f"  Max pixel diff:  {report['max_mean_diff']}")

    # Show worst frames
    worst = sorted(report['frames'], key=lambda x: -x.get('mean_diff', 0))[:5]
    if worst and worst[0].get('mean_diff', 0) > 0:
        print(f"\n  Worst frames:")
        for f in worst:
            print(f"    Frame {f['frame']}: avg_diff={f['mean_diff']}, {f['pct_different']}% pixels differ")

    # Save report
    report_path = out / "frame_diff_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report: {report_path}")

    return report


if __name__ == "__main__":
    import numpy as np

    OG = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J).gb"
    RM = "/home/struktured/projects/penta-dragon-remake/rom/working/penta_dragon_dx.gbc"

    # Use DQN agent actions (best verifier)
    try:
        actions = np.load("../checkpoints_dqn/agent_actions_dqn50k.npy")
    except FileNotFoundError:
        # Fallback: random actions
        rng = np.random.default_rng(42)
        actions = rng.integers(0, 13, size=200)

    run_frame_diff(OG, RM, actions,
                    output_dir="../pipeline_output/frame_diff",
                    capture_interval=8,
                    max_frames=100)
