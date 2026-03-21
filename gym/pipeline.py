"""
Full Verification Pipeline — orchestrates all 5 stages.

Stage 1: Ghidra-MCP static analysis → discover reward addresses
Stage 2: mGBA-MCP runtime analysis → watch memory changes
Stage 3: RL training → PPO/DQN agent on OG ROM
Stage 4: Policy transfer → agent plays remake, compare trajectories
Stage 5: Colorization verification → explore visual states for palette gaps

Usage:
    # Full pipeline
    uv run python gym/pipeline.py --og original.gb --remake remake.gbc --stages 1-5

    # Just train + compare (stages 3-4)
    uv run python gym/pipeline.py --og original.gb --remake remake.gbc --stages 3-4

    # Just compare with random exploration
    uv run python gym/pipeline.py --og original.gb --remake remake.gbc --stages 4 --random
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np


def stage1_ghidra_discovery(rom_path, output_dir):
    """Stage 1: Static analysis with Ghidra-MCP."""
    from ghidra_integration import build_ghidra_analysis_plan, merge_ghidra_results
    from re_discovery import RewardConfig, auto_discover

    print("\n" + "=" * 60)
    print("STAGE 1: Ghidra-MCP Static Analysis")
    print("=" * 60)

    plan = build_ghidra_analysis_plan(rom_path)
    print(f"Analysis plan: {len(plan['steps'])} steps")

    # Try to use Ghidra-MCP if available
    ghidra_results = None
    try:
        # This would use MCP tools when available
        # For now, use known patterns + any cached results
        cached = output_dir / "ghidra_cache.json"
        if cached.exists():
            with open(cached) as f:
                ghidra_results = json.load(f)
            print(f"  Loaded cached Ghidra results from {cached}")
    except Exception as e:
        print(f"  Ghidra-MCP not available: {e}")
        print("  Using known patterns + manual config")

    config = auto_discover(rom_path, ghidra_results=ghidra_results)
    print(f"  Discovered {len(config.addresses)} addresses")

    # Save config
    config_file = output_dir / "reward_config.json"
    with open(config_file, "w") as f:
        f.write(config.to_json())
    print(f"  Config saved to {config_file}")

    return config


def stage2_mgba_runtime(rom_path, config, output_dir, frames=600):
    """Stage 2: Runtime analysis with mGBA-MCP."""
    from mgba_integration import generate_scanner_lua, generate_state_dumper_lua
    from re_discovery import discover_from_runtime

    print("\n" + "=" * 60)
    print("STAGE 2: mGBA-MCP Runtime Analysis")
    print("=" * 60)

    # Generate scanner script
    scanner_lua = generate_scanner_lua("scan_results.txt", frames=frames)
    lua_file = output_dir / "auto_scanner.lua"
    lua_file.write_text(scanner_lua)
    print(f"  Scanner Lua generated: {lua_file}")

    # Generate state dumper for known addresses
    addrs = {a.name: a.addr for a in config.addresses}
    dumper_lua = generate_state_dumper_lua("state_dump.csv", addrs, frames=frames)
    dumper_file = output_dir / "auto_dumper.lua"
    dumper_file.write_text(dumper_lua)
    print(f"  State dumper Lua generated: {dumper_file}")

    # Try running headlessly
    scanner_output = ""
    scan_file = output_dir / "scan_results.txt"
    if scan_file.exists():
        scanner_output = scan_file.read_text()
        print(f"  Loaded cached scan results ({len(scanner_output)} bytes)")

    if scanner_output:
        new_addrs = discover_from_runtime(scanner_output)
        print(f"  Runtime discovery found {len(new_addrs)} new addresses")

        # Merge with config
        seen = {a.addr: a for a in config.addresses}
        for a in new_addrs:
            if a.addr not in seen or a.confidence > seen[a.addr].confidence:
                seen[a.addr] = a
        config.addresses = list(seen.values())

    return config


def stage3_train(rom_path, config, output_dir, algo="ppo",
                 total_timesteps=50000, cgb=False, frames_per_step=4,
                 max_steps=2048):
    """Stage 3: RL training on OG ROM."""
    from train import train_ppo, train_dqn

    print("\n" + "=" * 60)
    print(f"STAGE 3: RL Training ({algo.upper()}, {total_timesteps} steps)")
    print("=" * 60)

    reward_addrs = config.get_reward_addresses()
    state_addrs = config.get_state_addresses()

    print(f"  Reward addresses: {reward_addrs}")
    print(f"  State addresses: {state_addrs}")

    checkpoint_dir = str(output_dir / "checkpoints")
    log_dir = str(output_dir / "logs")

    train_fn = train_ppo if algo == "ppo" else train_dqn
    model = train_fn(
        rom_path=rom_path,
        reward_addresses=reward_addrs,
        state_addresses=state_addrs,
        total_timesteps=total_timesteps,
        checkpoint_dir=checkpoint_dir,
        cgb=cgb,
        frames_per_step=frames_per_step,
        max_steps=max_steps,
        log_dir=log_dir,
    )

    print(f"  Training complete. Model saved to {checkpoint_dir}")
    return model


def stage4_transfer(model, og_rom, remake_rom, config, output_dir,
                    n_steps=1000, og_cgb=False, rm_cgb=False,
                    frames_per_step=4, random_seed=None):
    """Stage 4: Policy transfer and trajectory comparison."""
    from policy_transfer import transfer_and_compare

    print("\n" + "=" * 60)
    print("STAGE 4: Policy Transfer & Comparison")
    print("=" * 60)

    reward_addrs = config.get_reward_addresses()
    state_addrs = config.get_state_addresses()

    model_path = None
    if model is not None:
        model_path = str(output_dir / "checkpoints" / "ppo_final")

    report, actions, og_traj, rm_traj = transfer_and_compare(
        model_path=model_path,
        og_rom=og_rom,
        remake_rom=remake_rom,
        reward_addresses=reward_addrs,
        state_addresses=state_addrs,
        n_steps=n_steps,
        og_cgb=og_cgb,
        rm_cgb=rm_cgb,
        frames_per_step=frames_per_step,
        random_seed=random_seed if model is None else None,
    )

    # Save results
    report_file = output_dir / "comparison_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)

    actions_file = output_dir / "agent_actions.npy"
    np.save(str(actions_file), actions)

    print(f"  Report saved to {report_file}")
    print(f"  Actions saved to {actions_file}")

    return report


def stage5_colorization(og_rom, remake_rom, config, output_dir,
                        n_steps=500, frames_per_step=4):
    """Stage 5: Colorization verification — explore visual states."""
    print("\n" + "=" * 60)
    print("STAGE 5: Colorization Verification")
    print("=" * 60)

    # For colorization, we need to compare palette registers and VRAM
    # between OG (DMG) and remake (CGB)
    color_addresses = {
        "BGP": 0xFF47,       # DMG BG palette
        "OBP0": 0xFF48,      # DMG OBJ palette 0
        "OBP1": 0xFF49,      # DMG OBJ palette 1
        "LCDC": 0xFF40,      # LCD control
        "SCX": 0xFF43,        # Scroll X
        "SCY": 0xFF42,        # Scroll Y
        "LY": 0xFF44,         # Current scanline
        "WX": 0xFF4B,         # Window X
        "WY": 0xFF4A,         # Window Y
    }

    # Add CGB-specific registers for remake
    cgb_registers = {
        "VBK": 0xFF4F,        # VRAM bank
        "BCPS": 0xFF68,       # BG color palette spec
        "BCPD": 0xFF69,       # BG color palette data
        "OCPS": 0xFF6A,       # OBJ color palette spec
        "OCPD": 0xFF6B,       # OBJ color palette data
    }

    # Generate Lua scripts for visual state comparison
    from mgba_integration import generate_state_dumper_lua

    og_dumper = generate_state_dumper_lua(
        "og_color_dump.csv", color_addresses, frames=n_steps * 4,
        sample_interval=4
    )
    rm_dumper = generate_state_dumper_lua(
        "rm_color_dump.csv", {**color_addresses, **cgb_registers},
        frames=n_steps * 4, sample_interval=4
    )

    og_lua_file = output_dir / "og_color_dumper.lua"
    rm_lua_file = output_dir / "rm_color_dumper.lua"
    og_lua_file.write_text(og_dumper)
    rm_lua_file.write_text(rm_dumper)

    print(f"  OG color dumper: {og_lua_file}")
    print(f"  Remake color dumper: {rm_lua_file}")
    print(f"  Run these with mGBA to compare visual states:")
    print(f"    mgba-qt -l {og_lua_file} {og_rom}")
    print(f"    mgba-qt -l {rm_lua_file} {remake_rom}")

    # Check for existing color dumps
    og_dump = output_dir / "og_color_dump.csv"
    rm_dump = output_dir / "rm_color_dump.csv"

    if og_dump.exists() and rm_dump.exists():
        print(f"\n  Found existing color dumps — comparing...")
        # Parse and compare
        import csv
        og_data = list(csv.DictReader(open(og_dump)))
        rm_data = list(csv.DictReader(open(rm_dump)))

        total = min(len(og_data), len(rm_data))
        if total > 0:
            shared_fields = set(og_data[0].keys()) & set(rm_data[0].keys()) - {"frame"}
            matches = {f: 0 for f in shared_fields}

            for i in range(total):
                for f in shared_fields:
                    if og_data[i].get(f) == rm_data[i].get(f):
                        matches[f] += 1

            print(f"  Compared {total} frames:")
            for f in sorted(shared_fields):
                pct = 100 * matches[f] // total
                print(f"    {f:8s}: {pct}%")
    else:
        print(f"\n  No color dumps found yet. Run the Lua scripts first.")

    return {"status": "scripts_generated"}


def run_pipeline(og_rom, remake_rom=None, stages="1-5", output_dir="pipeline_output",
                 algo="ppo", train_steps=50000, compare_steps=1000,
                 og_cgb=False, rm_cgb=False, frames_per_step=4,
                 random_exploration=False):
    """Run the full verification pipeline."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # Parse stages
    if "-" in stages:
        start, end = map(int, stages.split("-"))
        stage_list = list(range(start, end + 1))
    else:
        stage_list = [int(s) for s in stages.split(",")]

    print(f"\n{'#' * 60}")
    print(f"GB GAME VERIFIER — RL/RE PIPELINE")
    print(f"{'#' * 60}")
    print(f"OG ROM: {og_rom}")
    if remake_rom:
        print(f"Remake: {remake_rom}")
    print(f"Stages: {stage_list}")
    print(f"Output: {output}")

    config = None
    model = None
    report = None

    # Stage 1
    if 1 in stage_list:
        config = stage1_ghidra_discovery(og_rom, output)

    # Default config if stage 1 skipped
    if config is None:
        from re_discovery import PENTA_DRAGON_CONFIG
        config = PENTA_DRAGON_CONFIG

    # Stage 2
    if 2 in stage_list:
        config = stage2_mgba_runtime(og_rom, config, output)

    # Stage 3
    if 3 in stage_list and not random_exploration:
        model = stage3_train(
            og_rom, config, output, algo=algo,
            total_timesteps=train_steps, cgb=og_cgb,
            frames_per_step=frames_per_step,
        )

    # Stage 4
    if 4 in stage_list and remake_rom:
        report = stage4_transfer(
            model, og_rom, remake_rom, config, output,
            n_steps=compare_steps, og_cgb=og_cgb, rm_cgb=rm_cgb,
            frames_per_step=frames_per_step,
            random_seed=42 if random_exploration else None,
        )

    # Stage 5
    if 5 in stage_list and remake_rom:
        stage5_colorization(
            og_rom, remake_rom, config, output,
            n_steps=compare_steps, frames_per_step=frames_per_step,
        )

    # Summary
    print(f"\n{'#' * 60}")
    print("PIPELINE COMPLETE")
    print(f"{'#' * 60}")
    if report:
        rate = report.get("overall_match_rate", 0)
        print(f"  Overall match rate: {rate:.1%}")
        if rate >= 0.95:
            print("  VERDICT: PASS")
        elif rate >= 0.80:
            print("  VERDICT: WARN")
        else:
            print("  VERDICT: FAIL")
    print(f"  Output directory: {output}")

    return report


def main():
    parser = argparse.ArgumentParser(description="GB Verification Pipeline")
    parser.add_argument("--og", required=True, help="Original ROM")
    parser.add_argument("--remake", help="Remake/romhack ROM")
    parser.add_argument("--stages", default="1-5", help="Stages to run (e.g. '1-5', '3,4')")
    parser.add_argument("--algo", choices=["ppo", "dqn"], default="ppo")
    parser.add_argument("--train-steps", type=int, default=50000)
    parser.add_argument("--compare-steps", type=int, default=1000)
    parser.add_argument("--og-cgb", action="store_true")
    parser.add_argument("--rm-cgb", action="store_true")
    parser.add_argument("--frames-per-step", type=int, default=4)
    parser.add_argument("--output-dir", default="pipeline_output")
    parser.add_argument("--random", action="store_true",
                        help="Skip training, use random exploration")
    args = parser.parse_args()

    report = run_pipeline(
        og_rom=args.og,
        remake_rom=args.remake,
        stages=args.stages,
        output_dir=args.output_dir,
        algo=args.algo,
        train_steps=args.train_steps,
        compare_steps=args.compare_steps,
        og_cgb=args.og_cgb,
        rm_cgb=args.rm_cgb,
        frames_per_step=args.frames_per_step,
        random_exploration=args.random,
    )


if __name__ == "__main__":
    main()
