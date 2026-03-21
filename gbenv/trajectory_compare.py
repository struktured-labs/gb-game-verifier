"""
Trajectory Comparator — runs the same action sequence on two ROMs,
compares state trajectories frame-by-frame.

This is the RL-powered equivalent of the scripted verifier:
instead of hardcoded inputs, it uses agent-generated actions
that explore the game state space more thoroughly.

Usage:
    # Compare with random exploration
    python trajectory_compare.py --og original.gb --remake remake.gbc --steps 1000

    # Compare with recorded actions
    python trajectory_compare.py --og original.gb --remake remake.gbc --actions actions.npy
"""
import argparse
import numpy as np
import sys
from pathlib import Path

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_trajectory(rom_path, actions, state_addresses, frames_per_step=4, cgb=False):
    """Run a sequence of actions on a ROM, return state trajectory."""
    from gb_env import GBEnv

    env = GBEnv(
        rom_path,
        state_addresses=state_addresses,
        frames_per_step=frames_per_step,
        cgb=cgb,
        max_steps=len(actions) + 100,
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


def compare_trajectories(og_traj, rm_traj, exclude=None):
    """Compare two state trajectories, return divergences."""
    exclude = exclude or {"step"}
    total = min(len(og_traj), len(rm_traj))

    if total == 0:
        return {"error": "no data"}

    # Get all fields
    fields = set()
    for t in og_traj[:1] + rm_traj[:1]:
        fields.update(t.keys())
    fields -= exclude

    # Compare
    matches = {f: 0 for f in fields}
    divergences = []

    for i in range(total):
        for f in fields:
            og_val = og_traj[i].get(f, None)
            rm_val = rm_traj[i].get(f, None)
            if og_val == rm_val:
                matches[f] += 1
            elif i < 20:  # Only log first 20 divergences
                divergences.append({
                    "step": i,
                    "field": f,
                    "og": og_val,
                    "rm": rm_val,
                })

    # Report
    print(f"{'='*50}")
    print(f"TRAJECTORY COMPARISON — {total} steps")
    print(f"{'='*50}")

    for f in sorted(fields, key=lambda x: -matches.get(x, 0)):
        pct = 100 * matches[f] // total
        bar = "#" * (pct // 5) + "." * (20 - pct // 5)
        print(f"  {f:15s} [{bar}] {pct:3d}%")

    avg = sum(100 * m // total for m in matches.values()) // len(matches) if matches else 0
    print(f"\nAverage: {avg}%")

    if divergences:
        print(f"\nFirst divergences:")
        for d in divergences[:10]:
            print(f"  Step {d['step']}: {d['field']} OG={d['og']} RM={d['rm']}")

    return matches


def main():
    parser = argparse.ArgumentParser(description="Trajectory Comparator")
    parser.add_argument("--og", required=True, help="Original ROM")
    parser.add_argument("--remake", required=True, help="Remake/romhack ROM")
    parser.add_argument("--steps", type=int, default=500, help="Steps to run")
    parser.add_argument("--actions", help="Numpy file with recorded actions")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--cgb", action="store_true", help="CGB mode")
    args = parser.parse_args()

    # State addresses (Penta Dragon default — will be configurable)
    state_addrs = {
        "SCX": 0xFF43,
        "SCY": 0xFF42,
        "room": 0xFFBD,
        "form": 0xFFBE,
        "boss": 0xFFBF,
        "gameplay": 0xFFC1,
    }

    # Generate or load actions
    if args.actions:
        actions = np.load(args.actions)
    else:
        rng = np.random.default_rng(args.seed)
        actions = rng.integers(0, 13, size=args.steps)

    print(f"Running {len(actions)} actions on OG...")
    og_traj = run_trajectory(args.og, actions, state_addrs, cgb=args.cgb)
    print(f"  Captured {len(og_traj)} states")

    print(f"Running {len(actions)} actions on Remake...")
    rm_traj = run_trajectory(args.remake, actions, state_addrs, cgb=args.cgb)
    print(f"  Captured {len(rm_traj)} states")

    compare_trajectories(og_traj, rm_traj)


if __name__ == "__main__":
    main()
