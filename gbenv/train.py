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

import gymnasium as gym
import numpy as np


class MemoryObsWrapper(gym.ObservationWrapper):
    """Replace pixel observations with compact memory-state vector.

    Reads game state + OAM sprite positions as a flat float32 vector.
    Much more informative than 23k pixels for MlpPolicy.
    Observation: [SCX, SCY, room, form, boss, powerup, stage, hp, lives,
                  sprite0_y, sprite0_x, ..., sprite9_y, sprite9_x] = 29 values
    """
    MEM_ADDRS = [
        0xFF43,  # SCX
        0xFF42,  # SCY
        0xFFBD,  # room
        0xFFBE,  # form
        0xFFBF,  # boss
        0xFFC0,  # powerup
        0xFFD0,  # stage
        0xDCDD,  # hp
        0xFFDD,  # lives
    ]
    # First 10 OAM sprites (Y, X positions)
    OAM_SLOTS = 10

    def __init__(self, env):
        super().__init__(env)
        n = len(self.MEM_ADDRS) + self.OAM_SLOTS * 2
        self.observation_space = gym.spaces.Box(
            0.0, 1.0, (n,), dtype=np.float32
        )

    def observation(self, obs):
        vals = []
        for addr in self.MEM_ADDRS:
            vals.append(self.env.unwrapped._read_memory(addr) / 255.0)
        for slot in range(self.OAM_SLOTS):
            base = 0xFE00 + slot * 4
            vals.append(self.env.unwrapped._read_memory(base) / 255.0)      # Y
            vals.append(self.env.unwrapped._read_memory(base + 1) / 255.0)  # X
        return np.array(vals, dtype=np.float32)


class DownsampleAndChannelWrapper(gym.ObservationWrapper):
    """Downsample GB screen and add channel dim for CnnPolicy compatibility.

    Converts (144,160) grayscale -> (1, 36, 40) uint8 via 4x4 avg pooling.
    For CGB (144,160,3) -> (3, 36, 40) via channel-first + 4x4 pool.
    """
    def __init__(self, env, scale=4):
        super().__init__(env)
        old_space = env.observation_space
        old_shape = old_space.shape
        self.scale = scale
        if len(old_shape) == 2:
            # Grayscale DMG: (144,160) -> (1, 36, 40)
            new_h = old_shape[0] // scale
            new_w = old_shape[1] // scale
            self.observation_space = gym.spaces.Box(
                0, 255, (1, new_h, new_w), dtype=np.uint8
            )
        else:
            # CGB: (144,160,3) -> (3, 36, 40)
            new_h = old_shape[0] // scale
            new_w = old_shape[1] // scale
            self.observation_space = gym.spaces.Box(
                0, 255, (old_shape[2], new_h, new_w), dtype=np.uint8
            )

    def observation(self, obs):
        s = self.scale
        if len(obs.shape) == 2:
            # (144,160) -> avg pool -> (36,40) -> (1,36,40)
            h, w = obs.shape
            pooled = obs[:h//s*s, :w//s*s].reshape(h//s, s, w//s, s).mean(axis=(1,3)).astype(np.uint8)
            return pooled[np.newaxis, :, :]
        else:
            # (144,160,3) -> (3,36,40)
            h, w, c = obs.shape
            pooled = obs[:h//s*s, :w//s*s].reshape(h//s, s, w//s, s, c).mean(axis=(1,3)).astype(np.uint8)
            return pooled.transpose(2, 0, 1)


def make_env(rom_path, reward_addresses, state_addresses, frames_per_step=4,
             cgb=False, max_steps=4096, boot_frames=200, boot_sequence=None,
             use_cnn=False):
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
            boot_frames=boot_frames,
            boot_sequence=boot_sequence,
        )
        if use_cnn:
            env = DownsampleAndChannelWrapper(env, scale=4)
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
              frames_per_step=4, max_steps=4096, log_dir="logs",
              boot_frames=200, boot_sequence=None):
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
                      max_steps=max_steps, boot_frames=boot_frames,
                      boot_sequence=boot_sequence)
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
              frames_per_step=4, max_steps=4096, log_dir="logs",
              boot_frames=200, boot_sequence=None, use_cnn=False):
    """Train a DQN agent with epsilon-greedy exploration.

    When use_cnn=True, wraps observations via DownsampleAndChannelWrapper
    (144,160) -> (1,36,40) and uses CnnPolicy. Otherwise uses MlpPolicy
    (faster on CPU, suitable when reward signal is the primary learning driver).

    Epsilon-greedy: starts at 1.0, decays to 0.05 over 30% of training.
    """
    from stable_baselines3 import DQN
    from stable_baselines3.common.callbacks import CheckpointCallback
    from stable_baselines3.common.monitor import Monitor

    checkpoint_path = Path(checkpoint_dir)
    checkpoint_path.mkdir(parents=True, exist_ok=True)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    env_fn = make_env(rom_path, reward_addresses, state_addresses,
                      frames_per_step=frames_per_step, cgb=cgb,
                      max_steps=max_steps, boot_frames=boot_frames,
                      boot_sequence=boot_sequence, use_cnn=use_cnn)
    env = Monitor(env_fn())

    policy = "CnnPolicy" if use_cnn else "MlpPolicy"

    checkpoint_cb = CheckpointCallback(
        save_freq=10000,
        save_path=str(checkpoint_path),
        name_prefix="dqn_gb",
    )

    if resume_from:
        model = DQN.load(resume_from, env=env)
    else:
        model = DQN(
            policy,
            env,
            verbose=1,
            learning_rate=1e-4,
            buffer_size=20000,
            learning_starts=1000,
            batch_size=32,
            tau=1.0,
            gamma=0.99,
            train_freq=4,
            target_update_interval=1000,
            exploration_fraction=0.3,
            exploration_final_eps=0.05,
            tensorboard_log=str(log_path),
        )

    print(f"Training DQN ({policy}) for {total_timesteps} timesteps on {rom_path}")
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
             cgb=False, frames_per_step=4, max_steps=4096,
             boot_frames=200, boot_sequence=None, use_cnn=False):
    """Evaluate a trained model and return trajectory data."""
    env_fn = make_env(rom_path, reward_addresses, state_addresses,
                      frames_per_step=frames_per_step, cgb=cgb,
                      max_steps=max_steps, boot_frames=boot_frames,
                      boot_sequence=boot_sequence, use_cnn=use_cnn)
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
                   n_steps=1000, cgb=False, frames_per_step=4,
                   boot_frames=200, boot_sequence=None, use_cnn=False,
                   deterministic=False):
    """Record agent actions for trajectory comparison.

    Args:
        deterministic: If True, always pick the greedy action.
            If False (default), use model's built-in exploration
            (epsilon-greedy for DQN, stochastic for PPO).
    """
    env_fn = make_env(rom_path, reward_addresses, state_addresses,
                      frames_per_step=frames_per_step, cgb=cgb,
                      max_steps=n_steps + 100, boot_frames=boot_frames,
                      boot_sequence=boot_sequence, use_cnn=use_cnn)
    env = env_fn()

    obs, _ = env.reset()
    actions = []

    for _ in range(n_steps):
        action, _ = model.predict(obs, deterministic=deterministic)
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
    parser.add_argument("--use-cnn", action="store_true",
                        help="Use CnnPolicy with downsampled observations (slower, better for images)")
    args = parser.parse_args()

    # Load reward config
    if args.reward_config:
        reward_addrs, state_addrs = load_reward_config(args.reward_config)
        boot_seq = None
    else:
        # Default: Penta Dragon addresses + boot sequence
        from re_discovery import PENTA_DRAGON_CONFIG
        from gb_env import PentaDragonEnv
        reward_addrs = PENTA_DRAGON_CONFIG.get_reward_addresses()
        state_addrs = PENTA_DRAGON_CONFIG.get_state_addresses()
        boot_seq = PentaDragonEnv.BOOT_SEQUENCE

    use_cnn = args.use_cnn

    # Train
    train_fn = train_ppo if args.algo == "ppo" else train_dqn
    train_kwargs = dict(
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
        boot_frames=200,
        boot_sequence=boot_seq,
    )
    if args.algo == "dqn":
        train_kwargs["use_cnn"] = use_cnn
    model = train_fn(**train_kwargs)

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
        boot_frames=200,
        boot_sequence=boot_seq,
        use_cnn=use_cnn,
    )

    # Record actions for trajectory comparison
    if args.record_actions:
        print(f"\nRecording {args.record_steps} actions...")
        actions = record_actions(
            model, args.rom, reward_addrs, state_addrs,
            n_steps=args.record_steps,
            cgb=args.cgb,
            frames_per_step=args.frames_per_step,
            boot_frames=200,
            boot_sequence=boot_seq,
            use_cnn=use_cnn,
        )
        np.save(args.record_actions, actions)
        print(f"Actions saved to {args.record_actions}")


if __name__ == "__main__":
    main()
