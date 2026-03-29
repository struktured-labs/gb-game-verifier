"""
OAM Sprite Count Comparison — verifies the remake has similar
enemy/projectile density to the OG at matching game states.

This catches:
- Enemy spawn rate too low/high
- Projectiles not spawning or persisting too long
- Missing sprite types
- Sprite visibility issues
"""
import json
import sys
sys.path.insert(0, '.')


def compare_sprite_counts(og_rom, remake_rom, input_sequence,
                           frames=3000, sample_interval=200):
    """Run both ROMs with same inputs, compare sprite counts at intervals."""
    # Use mGBA Lua to count visible sprites at each sample point
    # For now, use PyBoy since mGBA MCP handles this better via tool calls
    from gb_env import GBEnv, PentaDragonEnv
    BOOT = PentaDragonEnv.BOOT_SEQUENCE
    SYNC = PentaDragonEnv.SYNC_ON

    results = {}
    for name, rom in [("OG", og_rom), ("Remake", remake_rom)]:
        env = GBEnv(rom, boot_frames=200, boot_sequence=BOOT,
                    sync_on=SYNC, frames_per_step=4, max_steps=frames//4 + 100)
        obs, info = env.reset()

        counts = []
        for step in range(frames // 4):
            action = 0  # NOOP by default
            # Apply input sequence
            frame = step * 4
            for inp in input_sequence:
                if abs(frame - inp["frame"]) < 4:
                    action = inp.get("action", 0)
                    break

            obs, _, _, _, info = env.step(action)

            if step % (sample_interval // 4) == 0:
                # Count visible OAM sprites
                visible = 0
                for slot in range(40):
                    y = env._read_memory(0xFE00 + slot * 4)
                    x = env._read_memory(0xFE00 + slot * 4 + 1)
                    if 0 < y < 160 and 0 < x < 168:
                        visible += 1
                counts.append({"step": step, "sprites": visible})

        env.close()
        results[name] = counts

    # Compare
    print(f"\n{'='*50}")
    print("SPRITE COUNT COMPARISON")
    print(f"{'='*50}")
    print(f"{'Step':>6} {'OG sprites':>12} {'RM sprites':>12} {'Diff':>6}")
    for i in range(min(len(results["OG"]), len(results["Remake"]))):
        og_c = results["OG"][i]["sprites"]
        rm_c = results["Remake"][i]["sprites"]
        diff = rm_c - og_c
        flag = " ***" if abs(diff) > 4 else ""
        print(f"{results['OG'][i]['step']:>6} {og_c:>12} {rm_c:>12} {diff:>+6}{flag}")

    og_avg = sum(r["sprites"] for r in results["OG"]) / len(results["OG"])
    rm_avg = sum(r["sprites"] for r in results["Remake"]) / len(results["Remake"])
    print(f"\nAvg: OG={og_avg:.1f}, Remake={rm_avg:.1f}, Ratio={rm_avg/og_avg:.2f}" if og_avg > 0 else "")

    return results


if __name__ == "__main__":
    OG = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J).gb"
    RM = "/home/struktured/projects/penta-dragon-remake/rom/working/penta_dragon_dx.gbc"

    # Simple RIGHT + A sequence
    inputs = [{"frame": f, "action": 3} for f in range(400, 2000, 50)]  # RIGHT
    inputs += [{"frame": f, "action": 1} for f in range(500, 2000, 100)]  # A

    compare_sprite_counts(OG, RM, inputs, frames=2000, sample_interval=200)
