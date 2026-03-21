"""
RE-Assisted Reward Discovery — uses reverse engineering tools to
automatically discover game state addresses for RL reward shaping.

Stage 1: Ghidra-MCP integration (static analysis)
Stage 2: mGBA-MCP integration (runtime analysis)

The discovered addresses are used to:
1. Shape RL rewards (HP changes, score increments, level transitions)
2. Configure the gym environment automatically
3. Set up verifier comparison fields

Architecture:
  Ghidra-MCP → find functions that write to RAM → identify HP/score/level
  mGBA-MCP → watch RAM during gameplay → correlate changes with events
  → Output: reward_config.yaml with addresses + semantics
"""
from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class DiscoveredAddress:
    """A game state address discovered via RE."""
    addr: int
    name: str
    role: str  # "reward", "state", "structural"
    semantics: str  # "hp", "score", "lives", "room", "boss", etc.
    confidence: float  # 0.0-1.0
    source: str  # "ghidra", "mgba", "scanner", "manual"
    notes: str = ""


@dataclass
class RewardConfig:
    """Configuration for RL reward shaping from discovered addresses."""
    game_name: str
    addresses: list[DiscoveredAddress] = field(default_factory=list)

    def get_reward_addresses(self) -> dict:
        """Get addresses suitable for GBEnv reward_addresses."""
        return {
            a.semantics: a.addr
            for a in self.addresses
            if a.role == "reward" and a.confidence > 0.5
        }

    def get_state_addresses(self) -> dict:
        """Get addresses suitable for GBEnv state_addresses."""
        return {
            a.name: a.addr
            for a in self.addresses
            if a.role in ("state", "reward") and a.confidence > 0.3
        }

    def to_yaml(self) -> str:
        """Export as YAML config for the verifier."""
        lines = [f"name: \"{self.game_name}\"", "addresses:"]
        for a in sorted(self.addresses, key=lambda x: x.addr):
            critical = "true" if a.role == "reward" else "false"
            lines.append(
                f"  - {{addr: 0x{a.addr:04X}, name: \"{a.name}\", "
                f"critical: {critical}, "
                f"desc: \"{a.semantics} ({a.source}, {a.confidence:.0%})\"}}"
            )
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps({
            "game": self.game_name,
            "addresses": [
                {
                    "addr": f"0x{a.addr:04X}",
                    "name": a.name,
                    "role": a.role,
                    "semantics": a.semantics,
                    "confidence": a.confidence,
                    "source": a.source,
                }
                for a in self.addresses
            ]
        }, indent=2)


# ============================================================
# Stage 1: Static Analysis (Ghidra-MCP)
# ============================================================

def discover_from_ghidra(rom_path: str, ghidra_results: Optional[dict] = None) -> list[DiscoveredAddress]:
    """
    Discover game state addresses from Ghidra static analysis.

    Strategies:
    1. Find functions that write to HRAM (FF80-FFFE) — likely game state
    2. Find functions that write to specific WRAM ranges — HP, score, etc.
    3. Look for comparison patterns (CP A, 0 → game over check)
    4. Find interrupt handlers (VBlank, Timer) → OAM DMA, scroll updates

    Args:
        rom_path: Path to ROM for reference
        ghidra_results: Pre-computed Ghidra analysis results (from MCP)

    Returns:
        List of discovered addresses with confidence scores
    """
    addresses = []

    # Hardware registers (universal — always relevant)
    hw_regs = [
        (0xFF40, "LCDC", "structural", "lcd_control", 1.0),
        (0xFF42, "SCY", "state", "scroll_y", 1.0),
        (0xFF43, "SCX", "state", "scroll_x", 1.0),
        (0xFF47, "BGP", "state", "bg_palette", 0.8),
        (0xFF48, "OBP0", "state", "obj_palette_0", 0.7),
        (0xFF49, "OBP1", "state", "obj_palette_1", 0.7),
    ]
    for addr, name, role, sem, conf in hw_regs:
        addresses.append(DiscoveredAddress(
            addr=addr, name=name, role=role,
            semantics=sem, confidence=conf, source="known_hw"
        ))

    # OAM (universal — sprite positions)
    addresses.append(DiscoveredAddress(
        addr=0xFE00, name="OAM0_Y", role="state",
        semantics="sprite_0_y", confidence=1.0, source="known_hw"
    ))
    addresses.append(DiscoveredAddress(
        addr=0xFE01, name="OAM0_X", role="state",
        semantics="sprite_0_x", confidence=1.0, source="known_hw"
    ))

    # If Ghidra results provided, analyze them
    if ghidra_results:
        # Look for HRAM writes in function decompilations
        for func in ghidra_results.get("functions", []):
            body = func.get("decompiled", "")
            # Pattern: LD (FF__), A — writes to HRAM
            for line in body.split("\n"):
                if "0xFF" in line and ("LD" in line or "write" in line.lower()):
                    # Extract address
                    import re
                    match = re.search(r'0xFF([0-9A-Fa-f]{2})', line)
                    if match:
                        hram_addr = 0xFF00 + int(match.group(1), 16)
                        if 0xFF80 <= hram_addr <= 0xFFFE:
                            addresses.append(DiscoveredAddress(
                                addr=hram_addr,
                                name=f"HRAM_{hram_addr:04X}",
                                role="state",
                                semantics="unknown_hram",
                                confidence=0.4,
                                source="ghidra",
                                notes=f"Written by {func.get('name', '?')}"
                            ))

    return addresses


# ============================================================
# Stage 2: Runtime Analysis (mGBA-MCP / Memory Scanner)
# ============================================================

def discover_from_runtime(scanner_output: str) -> list[DiscoveredAddress]:
    """
    Discover addresses from runtime memory scanning results.

    Parses output from lua/memory_scanner.lua and classifies
    addresses based on their behavior patterns.
    """
    addresses = []

    for line in scanner_output.strip().split("\n"):
        line = line.strip()
        if not line.startswith("0x"):
            continue

        parts = line.split(":")
        if len(parts) < 2:
            continue

        try:
            addr = int(parts[0].strip(), 16)
            rest = parts[1].strip()
            # Parse "initial -> new (frame N)"
            tokens = rest.split()
            initial = int(tokens[0])
            new_val = int(tokens[2])
            frame = int(tokens[3].strip("(frame)"))
        except (ValueError, IndexError):
            continue

        # Classify based on address range and value patterns
        role = "state"
        semantics = "unknown"
        confidence = 0.3

        if 0xFE00 <= addr <= 0xFE9F:
            semantics = "oam_data"
            confidence = 0.8
        elif 0xFF40 <= addr <= 0xFF4F:
            semantics = "lcd_register"
            confidence = 0.9
        elif 0xFF80 <= addr <= 0xFFFE:
            semantics = "hram_state"
            confidence = 0.5
            # High-value HRAM: likely game state
            if new_val == 1 and initial == 0:
                semantics = "flag_activation"
                confidence = 0.6
                role = "reward"
            elif new_val == 3 and initial == 0:
                semantics = "lives_counter"
                confidence = 0.7
                role = "reward"
            elif new_val == 255 and initial == 0:
                semantics = "timer_or_hp"
                confidence = 0.6
                role = "reward"
        elif 0xC000 <= addr <= 0xDFFF:
            semantics = "wram_state"
            confidence = 0.3

        addresses.append(DiscoveredAddress(
            addr=addr,
            name=f"ADDR_{addr:04X}",
            role=role,
            semantics=semantics,
            confidence=confidence,
            source="scanner",
            notes=f"{initial}→{new_val} at frame {frame}"
        ))

    return addresses


# ============================================================
# Combined Discovery Pipeline
# ============================================================

def auto_discover(
    rom_path: str,
    game_name: str = "Unknown Game",
    scanner_output: Optional[str] = None,
    ghidra_results: Optional[dict] = None,
) -> RewardConfig:
    """
    Full discovery pipeline — combines static + runtime analysis.

    Returns a RewardConfig ready for use with GBEnv.
    """
    config = RewardConfig(game_name=game_name)

    # Stage 1: Static analysis (Ghidra or known patterns)
    config.addresses.extend(discover_from_ghidra(rom_path, ghidra_results))

    # Stage 2: Runtime analysis (memory scanner results)
    if scanner_output:
        config.addresses.extend(discover_from_runtime(scanner_output))

    # Deduplicate by address (keep highest confidence)
    seen = {}
    for a in config.addresses:
        if a.addr not in seen or a.confidence > seen[a.addr].confidence:
            seen[a.addr] = a
    config.addresses = list(seen.values())

    return config


# Penta Dragon pre-built config (from our verified analysis)
PENTA_DRAGON_CONFIG = RewardConfig(
    game_name="Penta Dragon",
    addresses=[
        DiscoveredAddress(0xFF43, "SCX", "state", "scroll_x", 1.0, "verified"),
        DiscoveredAddress(0xFF42, "SCY", "state", "scroll_y", 1.0, "verified"),
        DiscoveredAddress(0xFFBD, "room", "reward", "room", 1.0, "verified"),
        DiscoveredAddress(0xFFBE, "form", "state", "sara_form", 1.0, "verified"),
        DiscoveredAddress(0xFFBF, "boss", "reward", "boss_flag", 1.0, "verified"),
        DiscoveredAddress(0xFFC0, "powerup", "state", "powerup", 1.0, "verified"),
        DiscoveredAddress(0xFFC1, "gameplay", "reward", "gameplay_active", 1.0, "verified"),
        DiscoveredAddress(0xFFD0, "stage", "state", "stage_flag", 1.0, "verified"),
        DiscoveredAddress(0xFFDD, "lives", "reward", "lives", 0.9, "scanner"),
        DiscoveredAddress(0xFFE5, "room2", "state", "room_alt", 0.8, "scanner"),
        DiscoveredAddress(0xDCBB, "timer", "state", "countdown", 0.7, "scanner"),
    ]
)


if __name__ == "__main__":
    # Demo: generate config from Penta Dragon
    config = PENTA_DRAGON_CONFIG
    print("=== YAML Config ===")
    print(config.to_yaml())
    print()
    print("=== Reward Addresses ===")
    print(config.get_reward_addresses())
    print()
    print("=== State Addresses ===")
    print(config.get_state_addresses())
