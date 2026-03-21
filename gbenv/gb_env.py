"""
Game Boy Gymnasium Environment — wraps PyBoy/mGBA for RL training.

Supports:
- Frame-step control (tick per action)
- Memory read/write for reward shaping
- Screen capture for observation
- Input injection (8 buttons)
- Configurable game-specific rewards via memory addresses

Usage:
    env = GBEnv("rom.gb", reward_addresses={"hp": 0xDCDD, "score": 0xFFE5})
    obs, info = env.reset()
    for _ in range(1000):
        action = env.action_space.sample()
        obs, reward, done, truncated, info = env.step(action)
"""
import gymnasium as gym
import numpy as np
from gymnasium import spaces
from pathlib import Path
from typing import Optional


# GB button bitmask mapping
GB_BUTTONS = {
    0: 0x01,   # A
    1: 0x02,   # B
    2: 0x04,   # SELECT
    3: 0x08,   # START
    4: 0x10,   # RIGHT
    5: 0x20,   # LEFT
    6: 0x40,   # UP
    7: 0x80,   # DOWN
}

# Combined actions (common in GB games)
GB_ACTIONS = {
    0: 0x00,    # NOOP
    1: 0x01,    # A
    2: 0x02,    # B
    3: 0x10,    # RIGHT
    4: 0x20,    # LEFT
    5: 0x40,    # UP
    6: 0x80,    # DOWN
    7: 0x11,    # RIGHT + A
    8: 0x21,    # LEFT + A
    9: 0x41,    # UP + A
    10: 0x81,   # DOWN + A
    11: 0x08,   # START
    12: 0x04,   # SELECT
}


class GBEnv(gym.Env):
    """Game Boy environment for Gymnasium."""

    metadata = {"render_modes": ["rgb_array", "human"], "render_fps": 60}

    def __init__(
        self,
        rom_path: str,
        reward_addresses: Optional[dict] = None,
        state_addresses: Optional[dict] = None,
        frames_per_step: int = 4,
        max_steps: int = 10000,
        cgb: bool = False,
        render_mode: str = "rgb_array",
        boot_frames: int = 120,
        boot_sequence: Optional[list] = None,
        sync_on: Optional[tuple] = None,
    ):
        """
        Args:
            rom_path: Path to GB/GBC ROM
            reward_addresses: {name: addr} for reward shaping (reads uint8)
            state_addresses: {name: addr} for info dict
            frames_per_step: Frames to advance per action (frame skip)
            max_steps: Max steps before truncation
            cgb: Force CGB mode
            render_mode: "rgb_array" or "human"
            boot_frames: Frames to skip for boot ROM
            boot_sequence: List of (button_name, hold_frames, wait_frames)
                to execute after boot. Button names: START, A, B, UP, DOWN,
                LEFT, RIGHT, SELECT. Use this to navigate title screens.
            sync_on: (addr, value, max_frames) — after boot sequence, wait
                until memory[addr]==value before starting. Ensures both OG and
                remake start from same game state regardless of boot timing.
        """
        super().__init__()

        self.rom_path = str(Path(rom_path).resolve())
        self.reward_addresses = reward_addresses or {}
        self.state_addresses = state_addresses or {}
        self.frames_per_step = frames_per_step
        self.max_steps = max_steps
        self.cgb = cgb
        self.render_mode = render_mode
        self.boot_frames = boot_frames
        self.boot_sequence = boot_sequence or []
        self.sync_on = sync_on

        # Action space: 13 discrete actions (NOOP + 8 buttons + 4 combos)
        self.action_space = spaces.Discrete(len(GB_ACTIONS))

        # Observation space: 160x144 screen (grayscale for DMG, RGB for CGB)
        if cgb:
            self.observation_space = spaces.Box(0, 255, (144, 160, 3), dtype=np.uint8)
        else:
            self.observation_space = spaces.Box(0, 255, (144, 160), dtype=np.uint8)

        self._pyboy = None
        self._step_count = 0
        self._prev_rewards = {}

    def _create_emulator(self):
        """Create PyBoy instance."""
        try:
            from pyboy import PyBoy
        except ImportError:
            raise ImportError("PyBoy required: uv pip install pyboy")

        kwargs = {"window": "null" if self.render_mode == "rgb_array" else "SDL2"}
        if self.cgb:
            kwargs["cgb"] = True

        self._pyboy = PyBoy(self.rom_path, **kwargs)

    def _read_memory(self, addr: int) -> int:
        """Read a byte from memory."""
        return self._pyboy.memory[addr]

    def _get_screen(self) -> np.ndarray:
        """Get current screen as numpy array."""
        img = self._pyboy.screen.image
        arr = np.array(img)
        if not self.cgb and len(arr.shape) == 3:
            # Convert RGB to grayscale for DMG
            arr = np.mean(arr[:, :, :3], axis=2).astype(np.uint8)
        return arr

    def _compute_reward(self) -> float:
        """Compute reward from memory address changes."""
        reward = 0.0
        for name, addr in self.reward_addresses.items():
            current = self._read_memory(addr)
            prev = self._prev_rewards.get(name, current)

            if name in ("hp", "health", "lives"):
                # Negative reward for losing HP/lives
                if current < prev:
                    reward -= (prev - current) * 0.1
            elif name in ("score", "kills", "progress"):
                # Positive reward for increasing score/progress
                if current > prev:
                    reward += (current - prev) * 0.1
            elif name in ("room", "level", "stage"):
                # Reward for advancing to new rooms
                if current != prev:
                    reward += 1.0
            elif name in ("boss", "boss_flag"):
                # Big reward for triggering boss
                if current != prev and current > 0:
                    reward += 5.0
            else:
                # Generic: reward for any change
                if current != prev:
                    reward += 0.01

            self._prev_rewards[name] = current

        # Dense exploration reward: reward screen changes (novel frames)
        # SCX/SCY changes indicate the player is making the game progress
        for scroll_name in ("SCX", "SCY"):
            addr = self.state_addresses.get(scroll_name)
            if addr:
                current = self._read_memory(addr)
                prev_key = f"_scroll_{scroll_name}"
                prev = self._prev_rewards.get(prev_key, current)
                if current != prev:
                    reward += 0.01  # Small reward for any scroll change
                self._prev_rewards[prev_key] = current

        # Action diversity bonus: penalize repeating the same action
        reward -= 0.001

        return reward

    def _get_info(self) -> dict:
        """Get additional state info from memory."""
        info = {"step": self._step_count}
        for name, addr in self.state_addresses.items():
            info[name] = self._read_memory(addr)
        for name, addr in self.reward_addresses.items():
            info[f"reward_{name}"] = self._read_memory(addr)
        return info

    def reset(self, seed=None, options=None):
        """Reset the environment."""
        super().reset(seed=seed)

        if self._pyboy is not None:
            self._pyboy.stop()
            self._pyboy = None

        self._create_emulator()
        self._step_count = 0
        self._prev_rewards = {}

        # Phase 1: Boot ROM / initial load
        for _ in range(self.boot_frames):
            self._pyboy.tick(1, False)

        # Phase 2: Execute boot sequence (navigate menus, start game)
        if self.boot_sequence:
            from pyboy.utils import WindowEvent
            BUTTON_MAP = {
                "A": (WindowEvent.PRESS_BUTTON_A, WindowEvent.RELEASE_BUTTON_A),
                "B": (WindowEvent.PRESS_BUTTON_B, WindowEvent.RELEASE_BUTTON_B),
                "START": (WindowEvent.PRESS_BUTTON_START, WindowEvent.RELEASE_BUTTON_START),
                "SELECT": (WindowEvent.PRESS_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_SELECT),
                "UP": (WindowEvent.PRESS_ARROW_UP, WindowEvent.RELEASE_ARROW_UP),
                "DOWN": (WindowEvent.PRESS_ARROW_DOWN, WindowEvent.RELEASE_ARROW_DOWN),
                "LEFT": (WindowEvent.PRESS_ARROW_LEFT, WindowEvent.RELEASE_ARROW_LEFT),
                "RIGHT": (WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.RELEASE_ARROW_RIGHT),
                "WAIT": (None, None),
            }
            for button, hold, wait in self.boot_sequence:
                press, release = BUTTON_MAP.get(button.upper(), (None, None))
                if press is not None:
                    self._pyboy.send_input(press)
                    for _ in range(hold):
                        self._pyboy.tick(1, False)
                    self._pyboy.send_input(release)
                for _ in range(wait):
                    self._pyboy.tick(1, False)

        # Phase 3: Sync — wait until specific memory condition is met
        if self.sync_on:
            sync_addr, sync_val, sync_max = self.sync_on
            for _ in range(sync_max):
                if self._read_memory(sync_addr) == sync_val:
                    break
                self._pyboy.tick(1, False)

        obs = self._get_screen()
        info = self._get_info()
        return obs, info

    def _press_buttons(self, action: int):
        """Send button presses via PyBoy WindowEvent API."""
        from pyboy.utils import WindowEvent
        PRESS_MAP = {
            0x01: (WindowEvent.PRESS_BUTTON_A, WindowEvent.RELEASE_BUTTON_A),
            0x02: (WindowEvent.PRESS_BUTTON_B, WindowEvent.RELEASE_BUTTON_B),
            0x04: (WindowEvent.PRESS_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_SELECT),
            0x08: (WindowEvent.PRESS_BUTTON_START, WindowEvent.RELEASE_BUTTON_START),
            0x10: (WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.RELEASE_ARROW_RIGHT),
            0x20: (WindowEvent.PRESS_ARROW_LEFT, WindowEvent.RELEASE_ARROW_LEFT),
            0x40: (WindowEvent.PRESS_ARROW_UP, WindowEvent.RELEASE_ARROW_UP),
            0x80: (WindowEvent.PRESS_ARROW_DOWN, WindowEvent.RELEASE_ARROW_DOWN),
        }
        keys = GB_ACTIONS.get(action, 0x00)
        pressed = []
        for bit, (press, release) in PRESS_MAP.items():
            if keys & bit:
                self._pyboy.send_input(press)
                pressed.append(release)
        return pressed

    def step(self, action: int):
        """Execute one action for frames_per_step frames."""
        # Press buttons
        releases = self._press_buttons(action)

        # Run frames
        for f in range(self.frames_per_step):
            self._pyboy.tick(1, False)

        # Release buttons
        for rel in releases:
            self._pyboy.send_input(rel)

        self._step_count += 1

        obs = self._get_screen()
        reward = self._compute_reward()
        done = False
        truncated = self._step_count >= self.max_steps
        info = self._get_info()

        return obs, reward, done, truncated, info

    def render(self):
        """Render current frame."""
        if self.render_mode == "rgb_array":
            return self._get_screen()

    def close(self):
        """Clean up."""
        if self._pyboy is not None:
            self._pyboy.stop()
            self._pyboy = None


class PentaDragonEnv(GBEnv):
    """Pre-configured environment for Penta Dragon.

    The OG Penta Dragon has a long boot sequence:
    - ~120 frames for boot ROM
    - Title screen with "OPENING START" / "GAME START"
    - Press DOWN to select "GAME START", then START
    - ~390 frames stage intro (shows stage name)
    - Then gameplay begins

    auto_start handles this automatically.
    """

    # Boot sequence: navigate OG title screen to "GAME START"
    # Multiple presses needed for OG menu. Short waits — sync_on does the real wait.
    BOOT_SEQUENCE = [
        # (button, hold_frames, wait_after_frames)
        ("WAIT", 0, 80),      # Wait for title screen to fully render
        ("DOWN", 5, 15),      # Move cursor to "GAME START"
        ("A", 5, 30),         # Confirm selection
        ("A", 5, 30),         # Dismiss any prompt
        ("START", 5, 30),     # Extra dismiss attempt
        ("A", 5, 10),         # Final — sync_on waits for gameplay
    ]

    # Sync: wait until FFC1=1 (gameplay active), up to 1000 frames.
    # This replaces the old fixed 400-frame wait and ensures both OG
    # and remake begin with section_timer near 0.
    SYNC_ON = (0xFFC1, 1, 1000)

    def __init__(self, rom_path: str, **kwargs):
        super().__init__(
            rom_path,
            reward_addresses={
                "room": 0xFFBD,
                "boss": 0xFFBF,
                "gameplay": 0xFFC1,
                # Note: DCDD always 0 during normal gameplay (verified).
                # FFDD is volatile scratch register, NOT lives.
                # Actual HP: C07D tilemap value (0xD0=full, 0xC8=damaged)
            },
            state_addresses={
                "SCX": 0xFF43,
                "SCY": 0xFF42,
                "form": 0xFFBE,
                "powerup": 0xFFC0,
                "stage": 0xFFD0,
                "hp_tile": 0xC07D,  # Actual HP display (0xD0=full)
            },
            frames_per_step=4,
            boot_frames=200,
            boot_sequence=kwargs.pop("boot_sequence", None) or self.BOOT_SEQUENCE,
            sync_on=kwargs.pop("sync_on", None) or self.SYNC_ON,
            **kwargs,
        )


# Quick test
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python gb_env.py rom.gb")
        sys.exit(1)

    env = GBEnv(sys.argv[1])
    obs, info = env.reset()
    print(f"Observation shape: {obs.shape}")
    print(f"Action space: {env.action_space}")
    print(f"Info: {info}")

    total_reward = 0
    for i in range(100):
        action = env.action_space.sample()
        obs, reward, done, truncated, info = env.step(action)
        total_reward += reward
        if i % 20 == 0:
            print(f"Step {i}: reward={reward:.3f} total={total_reward:.3f} info={info}")

    env.close()
    print(f"\nDone. Total reward: {total_reward:.3f}")
