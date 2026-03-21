"""
Ghidra-MCP Integration — static analysis for reward address discovery.

Uses Ghidra-MCP tools to:
1. Find functions that write to HRAM/WRAM game state addresses
2. Identify HP/score/lives logic from decompilation
3. Find level transition routines
4. Map interrupt handlers (VBlank, STAT) for timing analysis

When Ghidra-MCP is available, calls tools directly.
When not available, provides analysis templates for manual Ghidra use.

Requires: Ghidra running with HTTP bridge plugin on localhost:8080
"""
import json
import re
from dataclasses import dataclass
from typing import Optional

from re_discovery import DiscoveredAddress


# Common Game Boy patterns to search for
GB_PATTERNS = {
    "hram_write": {
        "description": "Writes to HRAM (FF80-FFFE) — likely game state",
        "instructions": ["LDH (a8),A", "LD (FF00+"],
        "address_range": (0xFF80, 0xFFFE),
    },
    "hp_decrement": {
        "description": "HP decrement pattern — DEC followed by compare/jump",
        "instructions": ["DEC A", "DEC (HL)", "SUB"],
        "context": "followed by CP 0 or JR Z (death check)",
    },
    "room_transition": {
        "description": "Room/level transition — writes to room counter",
        "instructions": ["INC A", "LD (FF"],
        "context": "modifies room/level/section counter",
    },
    "score_update": {
        "description": "Score increment — BCD addition pattern",
        "instructions": ["ADD A", "DAA", "LD ("],
        "context": "BCD arithmetic followed by memory store",
    },
    "boss_check": {
        "description": "Boss flag activation",
        "instructions": ["LD A,", "LDH (", "CP"],
        "context": "Sets boss flag and loads boss-specific data",
    },
    "interrupt_handler": {
        "description": "Interrupt entry points",
        "addresses": [0x0040, 0x0048, 0x0050, 0x0058, 0x0060],
        "context": "VBlank=0x40, LCDC=0x48, Timer=0x50, Serial=0x58, Joypad=0x60",
    },
}

# Known Game Boy memory map semantics
GB_MEMORY_SEMANTICS = {
    # IO Registers
    (0xFF00, 0xFF00): "joypad",
    (0xFF01, 0xFF02): "serial",
    (0xFF04, 0xFF07): "timer",
    (0xFF0F, 0xFF0F): "interrupt_flag",
    (0xFF10, 0xFF3F): "sound",
    (0xFF40, 0xFF4B): "lcd",
    (0xFF4F, 0xFF4F): "vram_bank",
    (0xFF50, 0xFF50): "boot_rom",
    (0xFF51, 0xFF55): "hdma",
    (0xFF68, 0xFF6B): "cgb_palettes",
    (0xFF70, 0xFF70): "wram_bank",
    (0xFFFF, 0xFFFF): "interrupt_enable",
    # HRAM (game-specific)
    (0xFF80, 0xFFFE): "hram_game_state",
    # WRAM
    (0xC000, 0xCFFF): "wram_bank0",
    (0xD000, 0xDFFF): "wram_bank1",
}


def analyze_function_for_state_writes(decompiled: str, func_name: str) -> list[DiscoveredAddress]:
    """Analyze decompiled function for game state writes."""
    addresses = []

    # Pattern 1: LDH writes — LD (FFxx), A
    for match in re.finditer(r'(?:LDH|LD)\s*\((?:0x)?FF([0-9A-Fa-f]{2})\)', decompiled):
        hram_addr = 0xFF00 + int(match.group(1), 16)
        if 0xFF80 <= hram_addr <= 0xFFFE:
            addresses.append(DiscoveredAddress(
                addr=hram_addr,
                name=f"HRAM_{hram_addr:04X}",
                role="state",
                semantics="unknown_hram",
                confidence=0.5,
                source="ghidra",
                notes=f"Written by {func_name}",
            ))

    # Pattern 2: WRAM writes — LD (C000+offset), A
    for match in re.finditer(r'(?:LD)\s*\((?:0x)?([CD][0-9A-Fa-f]{3})\)', decompiled):
        wram_addr = int(match.group(1), 16)
        if 0xC000 <= wram_addr <= 0xDFFF:
            addresses.append(DiscoveredAddress(
                addr=wram_addr,
                name=f"WRAM_{wram_addr:04X}",
                role="state",
                semantics="unknown_wram",
                confidence=0.3,
                source="ghidra",
                notes=f"Written by {func_name}",
            ))

    # Pattern 3: DEC/SUB near compare — potential HP logic
    if re.search(r'(?:DEC|SUB)\s+.*(?:CP|JR\s+Z|RET\s+Z)', decompiled, re.DOTALL):
        # This function likely manages a counter (HP, lives, timer)
        for addr_match in addresses:
            if addr_match.semantics == "unknown_hram":
                addr_match.semantics = "counter_decrement"
                addr_match.confidence = 0.6
                addr_match.role = "reward"

    # Pattern 4: INC near store — potential score/progress
    if re.search(r'(?:INC|ADD)\s+.*(?:LDH|LD\s*\()', decompiled, re.DOTALL):
        for addr_match in addresses:
            if addr_match.semantics in ("unknown_hram", "unknown_wram"):
                addr_match.semantics = "counter_increment"
                addr_match.confidence = 0.5

    return addresses


def build_ghidra_analysis_plan(rom_path: str) -> dict:
    """Build a plan for Ghidra analysis of a GB ROM.

    Returns a structured plan that can be executed by either:
    1. Ghidra-MCP tools (when available)
    2. Manual Ghidra analysis
    """
    return {
        "rom": rom_path,
        "steps": [
            {
                "step": 1,
                "action": "list_functions",
                "description": "Get all function entry points",
                "tool": "ghidra_find_functions" if True else "manual",
            },
            {
                "step": 2,
                "action": "find_interrupt_handlers",
                "description": "Locate VBlank (0x0040), LCDC (0x0048) handlers",
                "addresses": [0x0040, 0x0048, 0x0050],
                "tool": "ghidra_decompile",
            },
            {
                "step": 3,
                "action": "search_hram_writes",
                "description": "Find all LDH (FF80-FFFE) instructions",
                "tool": "ghidra_search_instructions",
                "pattern": "LDH",
            },
            {
                "step": 4,
                "action": "decompile_state_functions",
                "description": "Decompile functions that write to HRAM game state",
                "tool": "ghidra_decompile",
            },
            {
                "step": 5,
                "action": "find_comparison_patterns",
                "description": "Find CP A,0 / JR Z patterns (death/game-over checks)",
                "tool": "ghidra_search_instructions",
                "pattern": "CP 0x00",
            },
            {
                "step": 6,
                "action": "cross_reference_analysis",
                "description": "Get xrefs to discovered state addresses",
                "tool": "ghidra_get_xrefs",
            },
        ],
    }


def merge_ghidra_results(ghidra_output: dict) -> list[DiscoveredAddress]:
    """Merge results from multiple Ghidra analysis steps."""
    all_addresses = []

    for func in ghidra_output.get("functions", []):
        decompiled = func.get("decompiled", "")
        if decompiled:
            addrs = analyze_function_for_state_writes(decompiled, func.get("name", "?"))
            all_addresses.extend(addrs)

    # Deduplicate
    seen = {}
    for a in all_addresses:
        if a.addr not in seen or a.confidence > seen[a.addr].confidence:
            seen[a.addr] = a

    return list(seen.values())


if __name__ == "__main__":
    # Demo: show analysis plan
    plan = build_ghidra_analysis_plan("rom/Penta Dragon (J).gb")
    print("=== Ghidra Analysis Plan ===")
    for step in plan["steps"]:
        print(f"  Step {step['step']}: {step['description']}")
        print(f"    Tool: {step['tool']}")

    # Demo: analyze sample decompiled function
    sample = """
    PUSH AF
    LDH A,(FF43)     ; read SCX
    INC A
    LDH (FF43),A     ; write SCX
    LDH A,(FFBD)     ; read room counter
    CP 0x07
    JR Z,.done
    INC A
    LDH (FFBD),A     ; write room counter
    .done:
    POP AF
    RET
    """
    addrs = analyze_function_for_state_writes(sample, "scroll_handler")
    print("\n=== Discovered from sample ===")
    for a in addrs:
        print(f"  0x{a.addr:04X} {a.name}: {a.semantics} ({a.confidence:.0%})")
