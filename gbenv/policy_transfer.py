"""
Policy Transfer — trained agent plays OG and remake/romhack, compares trajectories.

This is the core verification step:
1. Load trained agent (from train.py)
2. Record agent actions on OG ROM
3. Replay exact same actions on remake/romhack ROM
4. Compare state trajectories frame-by-frame
5. Generate divergence report

Usage:
    # Compare OG vs remake using trained agent
    uv run python gym/policy_transfer.py \
        --model checkpoints/ppo_final \
        --og "rom/Penta Dragon (J).gb" \
        --remake "rom/penta_dragon_dx.gbc" \
        --steps 2000

    # Compare using pre-recorded actions
    uv run python gym/policy_transfer.py \
        --actions recorded_actions.npy \
        --og original.gb --remake remake.gbc

    # Random exploration comparison (no trained model needed)
    uv run python gym/policy_transfer.py \
        --random --og original.gb --remake remake.gbc --steps 500
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np


def run_with_model(model, rom_path, reward_addresses, state_addresses,
                   n_steps=1000, cgb=False, frames_per_step=4,
                   boot_frames=200, boot_sequence=None):
    """Run trained agent on a ROM, return (actions, trajectory)."""
    from gb_env import GBEnv

    env = GBEnv(
        rom_path=rom_path,
        reward_addresses=reward_addresses,
        state_addresses=state_addresses,
        frames_per_step=frames_per_step,
        cgb=cgb,
        max_steps=n_steps + 100,
        boot_frames=boot_frames,
        boot_sequence=boot_sequence,
    )

    obs, info = env.reset()
    actions = []
    trajectory = [info.copy()]

    for _ in range(n_steps):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, truncated, info = env.step(int(action))
        actions.append(int(action))
        trajectory.append(info.copy())
        if done or truncated:
            break

    env.close()
    return np.array(actions), trajectory


def replay_actions(rom_path, actions, reward_addresses, state_addresses,
                   cgb=False, frames_per_step=4, boot_frames=200,
                   boot_sequence=None):
    """Replay recorded actions on a ROM, return trajectory."""
    from gb_env import GBEnv

    env = GBEnv(
        rom_path=rom_path,
        reward_addresses=reward_addresses,
        state_addresses=state_addresses,
        frames_per_step=frames_per_step,
        cgb=cgb,
        max_steps=len(actions) + 100,
        boot_frames=boot_frames,
        boot_sequence=boot_sequence,
    )

    obs, info = env.reset()
    trajectory = [info.copy()]

    for action in actions:
        obs, reward, done, truncated, info = env.step(int(action))
        trajectory.append(info.copy())
        if done or truncated:
            break

    env.close()
    return trajectory


def compare_trajectories(og_traj, rm_traj, exclude=None, verbose=True):
    """Compare two trajectories, return detailed divergence report."""
    exclude = exclude or {"step"}
    total = min(len(og_traj), len(rm_traj))

    if total == 0:
        return {"error": "no data", "match_rate": 0.0}

    # Get all fields
    fields = set()
    for t in og_traj[:1] + rm_traj[:1]:
        fields.update(t.keys())
    fields -= exclude

    # Compare
    matches = {f: 0 for f in fields}
    first_divergence = {f: None for f in fields}
    divergences = []

    for i in range(total):
        for f in fields:
            og_val = og_traj[i].get(f)
            rm_val = rm_traj[i].get(f)
            if og_val == rm_val:
                matches[f] += 1
            else:
                if first_divergence[f] is None:
                    first_divergence[f] = i
                if len(divergences) < 100:
                    divergences.append({
                        "step": i, "field": f,
                        "og": og_val, "rm": rm_val,
                    })

    # Compute per-field match rates
    field_rates = {}
    for f in sorted(fields, key=lambda x: -matches.get(x, 0)):
        rate = matches[f] / total
        field_rates[f] = rate

    overall = np.mean(list(field_rates.values())) if field_rates else 0.0

    report = {
        "total_steps": total,
        "overall_match_rate": float(overall),
        "field_rates": field_rates,
        "first_divergence": {f: v for f, v in first_divergence.items() if v is not None},
        "divergence_count": len(divergences),
        "divergences": divergences[:20],
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"TRAJECTORY COMPARISON — {total} steps")
        print(f"{'='*60}")
        for f, rate in sorted(field_rates.items(), key=lambda x: -x[1]):
            pct = int(rate * 100)
            bar = "#" * (pct // 5) + "." * (20 - pct // 5)
            div_at = first_divergence.get(f)
            div_str = f" (first div @ step {div_at})" if div_at is not None else ""
            print(f"  {f:20s} [{bar}] {pct:3d}%{div_str}")

        print(f"\n  Overall match rate: {overall:.1%}")

        if divergences:
            print(f"\n  First divergences:")
            shown = set()
            for d in divergences:
                key = d["field"]
                if key not in shown:
                    print(f"    Step {d['step']:4d}: {key} OG={d['og']} RM={d['rm']}")
                    shown.add(key)
                    if len(shown) >= 10:
                        break

    return report


def transfer_and_compare(model_path, og_rom, remake_rom, reward_addresses,
                         state_addresses, n_steps=1000, og_cgb=False,
                         rm_cgb=False, frames_per_step=4,
                         actions_path=None, random_seed=None,
                         og_boot_sequence=None, rm_boot_sequence=None,
                         boot_frames=200):
    """Full pipeline: train/load → record on OG → replay on remake → compare."""
    from stable_baselines3 import PPO, DQN

    # Get actions
    if actions_path:
        print(f"Loading recorded actions from {actions_path}")
        actions = np.load(actions_path)
    elif random_seed is not None:
        print(f"Generating {n_steps} random actions (seed={random_seed})")
        rng = np.random.default_rng(random_seed)
        actions = rng.integers(0, 13, size=n_steps)
    elif model_path:
        print(f"Loading model from {model_path}")
        # Try PPO first, then DQN
        try:
            model = PPO.load(model_path)
        except Exception:
            model = DQN.load(model_path)

        print(f"Recording {n_steps} agent actions on OG ROM...")
        actions, og_traj = run_with_model(
            model, og_rom, reward_addresses, state_addresses,
            n_steps=n_steps, cgb=og_cgb, frames_per_step=frames_per_step,
            boot_frames=boot_frames, boot_sequence=og_boot_sequence,
        )
        print(f"  Recorded {len(actions)} actions, {len(og_traj)} states")
    else:
        raise ValueError("Must provide --model, --actions, or --random")

    # If we didn't already get OG trajectory from model run, replay on OG
    if not model_path or actions_path or random_seed is not None:
        print(f"Replaying {len(actions)} actions on OG ROM...")
        og_traj = replay_actions(
            og_rom, actions, reward_addresses, state_addresses,
            cgb=og_cgb, frames_per_step=frames_per_step,
            boot_frames=boot_frames, boot_sequence=og_boot_sequence,
        )
        print(f"  Captured {len(og_traj)} states")

    # Replay on remake (may need different boot sequence)
    rm_boot = rm_boot_sequence if rm_boot_sequence is not None else og_boot_sequence
    print(f"Replaying {len(actions)} actions on remake ROM...")
    rm_traj = replay_actions(
        remake_rom, actions, reward_addresses, state_addresses,
        cgb=rm_cgb, frames_per_step=frames_per_step,
        boot_frames=boot_frames, boot_sequence=rm_boot,
    )
    print(f"  Captured {len(rm_traj)} states")

    # Compare
    report = compare_trajectories(og_traj, rm_traj)

    return report, actions, og_traj, rm_traj


def main():
    parser = argparse.ArgumentParser(description="Policy Transfer Comparator")
    parser.add_argument("--og", required=True, help="Original ROM path")
    parser.add_argument("--remake", required=True, help="Remake/romhack ROM path")
    parser.add_argument("--model", help="Trained model checkpoint")
    parser.add_argument("--actions", help="Pre-recorded actions (.npy)")
    parser.add_argument("--random", action="store_true", help="Use random actions")
    parser.add_argument("--steps", type=int, default=1000, help="Number of steps")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--og-cgb", action="store_true", help="OG in CGB mode")
    parser.add_argument("--rm-cgb", action="store_true", help="Remake in CGB mode")
    parser.add_argument("--frames-per-step", type=int, default=4)
    parser.add_argument("--reward-config", help="JSON reward config")
    parser.add_argument("--save-actions", help="Save actions to .npy")
    parser.add_argument("--save-report", help="Save report to .json")
    args = parser.parse_args()

    # Load reward config
    if args.reward_config:
        from train import load_reward_config
        reward_addrs, state_addrs = load_reward_config(args.reward_config)
        og_boot_seq = None
    else:
        from re_discovery import PENTA_DRAGON_CONFIG
        from gb_env import PentaDragonEnv
        reward_addrs = PENTA_DRAGON_CONFIG.get_reward_addresses()
        state_addrs = PENTA_DRAGON_CONFIG.get_state_addresses()
        og_boot_seq = PentaDragonEnv.BOOT_SEQUENCE

    report, actions, og_traj, rm_traj = transfer_and_compare(
        model_path=args.model,
        og_rom=args.og,
        remake_rom=args.remake,
        reward_addresses=reward_addrs,
        state_addresses=state_addrs,
        n_steps=args.steps,
        og_cgb=args.og_cgb,
        rm_cgb=args.rm_cgb,
        frames_per_step=args.frames_per_step,
        actions_path=args.actions,
        random_seed=args.seed if args.random else None,
        og_boot_sequence=og_boot_seq,
    )

    if args.save_actions:
        np.save(args.save_actions, actions)
        print(f"\nActions saved to {args.save_actions}")

    if args.save_report:
        with open(args.save_report, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Report saved to {args.save_report}")

    # Exit code based on match rate
    if report["overall_match_rate"] >= 0.95:
        print("\nVERDICT: PASS (>=95% match)")
        sys.exit(0)
    elif report["overall_match_rate"] >= 0.80:
        print(f"\nVERDICT: WARN ({report['overall_match_rate']:.0%} match)")
        sys.exit(0)
    else:
        print(f"\nVERDICT: FAIL ({report['overall_match_rate']:.0%} match)")
        sys.exit(1)


if __name__ == "__main__":
    main()
