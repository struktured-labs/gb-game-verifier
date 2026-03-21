"""
RL Training Loop — trains a PPO/DQN agent on a Game Boy ROM.

Uses memory-based reward shaping from RE-discovered addresses to guide
exploration toward game-meaningful states (room transitions, boss fights,
power-ups, deaths).

Usage:
    # Train on Penta Dragon OG ROM
    uv run python gym/train.py --rom "rom/Penta Dragon (J).gb" --steps 100000

    # Train with custom reward config
    uv run python gym/train.py --rom game.gb --reward-config rewards.json --steps 50000

    # Resume training from checkpoint
    uv run python gym/train.py --rom game.gb --resume checkpoints/ppo_latest
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np


def make_env(rom_path, reward_addresses, state_addresses, frames_per_step=4,
             cgb=False, max_steps=4096):
    """Create a wrapped GB environment for SB3 training."""
    from gb_env import GBEnv

    def _init():
        env = GBEnv(
            rom_path=rom_path,
            reward_addresses=reward_addresses,
            state_addresses=state_addresses,
            frames_per_step=frames_per_step,
            cgb=cgb,
            max_steps=max_steps,
        )
        return env

    return _init


def load_reward_config(config_path):
    """Load reward config from JSON file."""
    with open(config_path) as f:
        data = json.load(f)

    reward_addrs = {}
    state_addrs = {}
    for entry in data.get("addresses", []):
        addr = int(entry["addr"], 16) if isinstance(entry["addr"], str) else entry["addr"]
        if entry.get("role") == "reward":
            reward_addrs[entry["semantics"]] = addr
        else:
            state_addrs[entry["name"]] = addr

    return reward_addrs, state_addrs


def train_ppo(rom_path, reward_addresses, state_addresses, total_timesteps=100000,
              checkpoint_dir="checkpoints", resume_from=None, cgb=False,
              frames_per_step=4, max_steps=4096, log_dir="logs"):
    """Train a PPO agent on the given ROM."""
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    from stable_baselines3.common.monitor import Monitor

    checkpoint_path = Path(checkpoint_dir)
    checkpoint_path.mkdir(parents=True, exist_ok=True)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Create environment
    env_fn = make_env(rom_path, reward_addresses, state_addresses,
                      frames_per_step=frames_per_step, cgb=cgb,
                      max_steps=max_steps)
    env = Monitor(env_fn())

    # Callbacks
    checkpoint_cb = CheckpointCallback(
        save_freq=10000,
        save_path=str(checkpoint_path),
        name_prefix="ppo_gb",
    )

    if resume_from:
        print(f"Resuming from {resume_from}")
        model = PPO.load(resume_from, env=env)
    else:
        model = PPO(
            "MlpPolicy",
            env,
            verbose=1,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            tensorboard_log=str(log_path),
        )

    print(f"Training PPO for {total_timesteps} timesteps on {rom_path}")
    print(f"  Reward addresses: {reward_addresses}")
    print(f"  State addresses: {state_addresses}")
    print(f"  Frames per step: {frames_per_step}")
    print(f"  Max steps per episode: {max_steps}")

    model.learn(
        total_timesteps=total_timesteps,
        callback=checkpoint_cb,
        progress_bar=True,
    )

    # Save final model
    final_path = checkpoint_path / "ppo_final"
    model.save(str(final_path))
    print(f"Model saved to {final_path}")

    env.close()
    return model


def train_dqn(rom_path, reward_addresses, state_addresses, total_timesteps=100000,
              checkpoint_dir="checkpoints", resume_from=None, cgb=False,
              frames_per_step=4, max_steps=4096, log_dir="logs"):
    """Train a DQN agent on the given ROM."""
    from stable_baselines3 import DQN
    from stable_baselines3.common.callbacks import CheckpointCallback
    from stable_baselines3.common.monitor import Monitor

    checkpoint_path = Path(checkpoint_dir)
    checkpoint_path.mkdir(parents=True, exist_ok=True)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    env_fn = make_env(rom_path, reward_addresses, state_addresses,
                      frames_per_step=frames_per_step, cgb=cgb,
                      max_steps=max_steps)
    env = Monitor(env_fn())

    checkpoint_cb = CheckpointCallback(
        save_freq=10000,
        save_path=str(checkpoint_path),
        name_prefix="dqn_gb",
    )

    if resume_from:
        model = DQN.load(resume_from, env=env)
    else:
        model = DQN(
            "MlpPolicy",
            env,
            verbose=1,
            learning_rate=1e-4,
            buffer_size=50000,
            learning_starts=1000,
            batch_size=32,
            tau=1.0,
            gamma=0.99,
            train_freq=4,
            target_update_interval=1000,
            exploration_fraction=0.1,
            exploration_final_eps=0.02,
            tensorboard_log=str(log_path),
        )

    print(f"Training DQN for {total_timesteps} timesteps on {rom_path}")
    model.learn(
        total_timesteps=total_timesteps,
        callback=checkpoint_cb,
        progress_bar=True,
    )

    final_path = checkpoint_path / "dqn_final"
    model.save(str(final_path))
    print(f"Model saved to {final_path}")

    env.close()
    return model


def evaluate(model, rom_path, reward_addresses, state_addresses, n_episodes=5,
             cgb=False, frames_per_step=4, max_steps=4096):
    """Evaluate a trained model and return trajectory data."""
    env_fn = make_env(rom_path, reward_addresses, state_addresses,
                      frames_per_step=frames_per_step, cgb=cgb,
                      max_steps=max_steps)
    env = env_fn()

    all_rewards = []
    all_trajectories = []

    for ep in range(n_episodes):
        obs, info = env.reset()
        trajectory = [info.copy()]
        total_reward = 0
        actions = []

        done = False
        truncated = False
        while not done and not truncated:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(int(action))
            total_reward += reward
            trajectory.append(info.copy())
            actions.append(int(action))

        all_rewards.append(total_reward)
        all_trajectories.append({
            "episode": ep,
            "total_reward": total_reward,
            "steps": len(actions),
            "actions": actions,
            "trajectory": trajectory,
        })

        print(f"  Episode {ep+1}/{n_episodes}: reward={total_reward:.2f}, steps={len(actions)}")

    env.close()

    avg_reward = np.mean(all_rewards)
    print(f"\nAverage reward over {n_episodes} episodes: {avg_reward:.2f}")

    return all_trajectories


def record_actions(model, rom_path, reward_addresses, state_addresses,
                   n_steps=1000, cgb=False, frames_per_step=4):
    """Record agent actions for trajectory comparison."""
    env_fn = make_env(rom_path, reward_addresses, state_addresses,
                      frames_per_step=frames_per_step, cgb=cgb,
                      max_steps=n_steps + 100)
    env = env_fn()

    obs, _ = env.reset()
    actions = []

    for _ in range(n_steps):
        action, _ = model.predict(obs, deterministic=True)
        obs, _, done, truncated, _ = env.step(int(action))
        actions.append(int(action))
        if done or truncated:
            break

    env.close()
    return np.array(actions)


def main():
    parser = argparse.ArgumentParser(description="Train RL agent on Game Boy ROM")
    parser.add_argument("--rom", required=True, help="Path to GB/GBC ROM")
    parser.add_argument("--algo", choices=["ppo", "dqn"], default="ppo",
                        help="RL algorithm (default: ppo)")
    parser.add_argument("--steps", type=int, default=100000,
                        help="Total training timesteps")
    parser.add_argument("--max-ep-steps", type=int, default=4096,
                        help="Max steps per episode")
    parser.add_argument("--frames-per-step", type=int, default=4,
                        help="Frames to advance per action")
    parser.add_argument("--cgb", action="store_true", help="CGB mode")
    parser.add_argument("--resume", help="Resume from checkpoint")
    parser.add_argument("--reward-config", help="JSON reward config file")
    parser.add_argument("--checkpoint-dir", default="checkpoints")
    parser.add_argument("--log-dir", default="logs")
    parser.add_argument("--eval-episodes", type=int, default=5,
                        help="Episodes for post-training evaluation")
    parser.add_argument("--record-actions", help="Save recorded actions to .npy file")
    parser.add_argument("--record-steps", type=int, default=1000,
                        help="Steps to record")
    args = parser.parse_args()

    # Load reward config
    if args.reward_config:
        reward_addrs, state_addrs = load_reward_config(args.reward_config)
    else:
        # Default: Penta Dragon addresses
        from re_discovery import PENTA_DRAGON_CONFIG
        reward_addrs = PENTA_DRAGON_CONFIG.get_reward_addresses()
        state_addrs = PENTA_DRAGON_CONFIG.get_state_addresses()

    # Train
    train_fn = train_ppo if args.algo == "ppo" else train_dqn
    model = train_fn(
        rom_path=args.rom,
        reward_addresses=reward_addrs,
        state_addresses=state_addrs,
        total_timesteps=args.steps,
        checkpoint_dir=args.checkpoint_dir,
        resume_from=args.resume,
        cgb=args.cgb,
        frames_per_step=args.frames_per_step,
        max_steps=args.max_ep_steps,
        log_dir=args.log_dir,
    )

    # Evaluate
    print(f"\n{'='*50}")
    print("POST-TRAINING EVALUATION")
    print(f"{'='*50}")
    trajectories = evaluate(
        model, args.rom, reward_addrs, state_addrs,
        n_episodes=args.eval_episodes,
        cgb=args.cgb,
        frames_per_step=args.frames_per_step,
        max_steps=args.max_ep_steps,
    )

    # Record actions for trajectory comparison
    if args.record_actions:
        print(f"\nRecording {args.record_steps} actions...")
        actions = record_actions(
            model, args.rom, reward_addrs, state_addrs,
            n_steps=args.record_steps,
            cgb=args.cgb,
            frames_per_step=args.frames_per_step,
        )
        np.save(args.record_actions, actions)
        print(f"Actions saved to {args.record_actions}")


if __name__ == "__main__":
    main()
