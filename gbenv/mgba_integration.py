"""
mGBA-MCP Integration — runtime memory analysis for reward discovery.

Uses mGBA-MCP tools to:
1. Watch memory during gameplay for dynamic state changes
2. Correlate memory changes with game events
3. Auto-discover reward signals and state addresses
4. Profile timing and interrupts

When mGBA-MCP is not available, falls back to Lua scripting via
subprocess (same state_dumper.lua / memory_scanner.lua scripts).
"""
import json
import subprocess
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class MemoryWatch:
    """A memory address being watched during runtime analysis."""
    addr: int
    initial: int
    current: int
    changes: list  # [(frame, old_val, new_val), ...]

    @property
    def change_count(self):
        return len(self.changes)

    @property
    def is_counter(self):
        """Heuristic: monotonically increasing values suggest a counter."""
        if len(self.changes) < 2:
            return False
        vals = [self.initial] + [c[2] for c in self.changes]
        return all(vals[i] <= vals[i+1] for i in range(len(vals)-1))

    @property
    def is_flag(self):
        """Heuristic: only 0/1 values suggest a boolean flag."""
        vals = {self.initial, self.current} | {c[2] for c in self.changes}
        return vals <= {0, 1}

    @property
    def is_timer(self):
        """Heuristic: decrementing values suggest a countdown timer."""
        if len(self.changes) < 2:
            return False
        vals = [self.initial] + [c[2] for c in self.changes]
        return all(vals[i] >= vals[i+1] for i in range(len(vals)-1))


def generate_scanner_lua(output_path: str, scan_ranges: list = None,
                         frames: int = 300, sample_interval: int = 10) -> str:
    """Generate a Lua script for mGBA memory scanning.

    Returns the Lua script content. Can be run via mGBA-MCP's mgba_run_lua
    or directly via mGBA CLI.
    """
    if scan_ranges is None:
        scan_ranges = [
            (0xC000, 0xC0FF),  # WRAM page 0 start
            (0xDC00, 0xDCFF),  # WRAM — common game state area
            (0xFE00, 0xFE9F),  # OAM
            (0xFF40, 0xFF4F),  # LCD registers
            (0xFF80, 0xFFFE),  # HRAM
        ]

    range_init = "\n".join(
        f"    scan_range(0x{lo:04X}, 0x{hi:04X})"
        for lo, hi in scan_ranges
    )

    lua = f"""-- Auto-generated memory scanner
-- Scans specified ranges, logs changes

local initial = {{}}
local changes = {{}}
local frame_count = 0
local done = false

function scan_range(lo, hi)
    for addr = lo, hi do
        local val = emu:read8(addr)
        if initial[addr] == nil then
            initial[addr] = val
        elseif val ~= initial[addr] then
            if changes[addr] == nil then
                changes[addr] = {{}}
            end
            table.insert(changes[addr], {{
                frame = frame_count,
                old = initial[addr],
                new = val
            }})
            initial[addr] = val
        end
    end
end

function on_frame()
    if done then return end
    frame_count = frame_count + 1

    if frame_count % {sample_interval} == 0 then
{range_init}
    end

    if frame_count >= {frames} then
        done = true
        -- Write results
        local f = io.open("{output_path}", "w")
        if f then
            for addr, chgs in pairs(changes) do
                for _, c in ipairs(chgs) do
                    f:write(string.format("0x%04X: %d -> %d (frame %d)\\n",
                            addr, c.old, c.new, c.frame))
                end
            end
            f:close()
        end
        print("Scanner done: " .. frame_count .. " frames scanned")
    end
end

callbacks:add("frame", on_frame)

-- Initial scan
for addr = 0xC000, 0xC0FF do initial[addr] = emu:read8(addr) end
for addr = 0xDC00, 0xDCFF do initial[addr] = emu:read8(addr) end
for addr = 0xFE00, 0xFE9F do initial[addr] = emu:read8(addr) end
for addr = 0xFF40, 0xFF4F do initial[addr] = emu:read8(addr) end
for addr = 0xFF80, 0xFFFE do initial[addr] = emu:read8(addr) end

print("Memory scanner started — scanning " .. {frames} .. " frames")
"""
    return lua


def generate_state_dumper_lua(output_path: str, addresses: dict,
                              frames: int = 300, sample_interval: int = 1) -> str:
    """Generate a Lua script that dumps specific addresses every N frames."""
    addr_reads = "\n".join(
        f'        row = row .. "," .. emu:read8(0x{addr:04X})'
        for name, addr in sorted(addresses.items(), key=lambda x: x[1])
    )

    header_fields = ",".join(
        f"{name}" for name, addr in sorted(addresses.items(), key=lambda x: x[1])
    )

    lua = f"""-- Auto-generated state dumper
local frame_count = 0
local done = false
local f = io.open("{output_path}", "w")
f:write("frame,{header_fields}\\n")

function on_frame()
    if done then return end
    frame_count = frame_count + 1

    if frame_count % {sample_interval} == 0 then
        local row = tostring(frame_count)
{addr_reads}
        f:write(row .. "\\n")
    end

    if frame_count >= {frames} then
        done = true
        f:close()
        print("State dump done: " .. frame_count .. " frames")
    end
end

callbacks:add("frame", on_frame)
print("State dumper started — {frames} frames, interval={sample_interval}")
"""
    return lua


def run_scanner_headless(rom_path: str, frames: int = 300,
                         scan_ranges: list = None,
                         keys_sequence: list = None) -> str:
    """Run memory scanner headlessly via mGBA, return raw output."""
    work_dir = Path(rom_path).parent
    output_file = work_dir / "scanner_output.txt"
    lua_file = work_dir / "auto_scanner.lua"

    lua_content = generate_scanner_lua(
        str(output_file.name),  # Relative path for mGBA Lua
        scan_ranges=scan_ranges,
        frames=frames,
    )

    lua_file.write_text(lua_content)

    cmd = [
        "xvfb-run", "-a", "mgba-qt",
        "-l", str(lua_file),
        str(rom_path),
    ]

    env = os.environ.copy()
    env.update({
        "QT_QPA_PLATFORM": "offscreen",
        "SDL_AUDIODRIVER": "dummy",
    })
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)

    try:
        result = subprocess.run(
            cmd, cwd=str(work_dir), env=env,
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        pass  # Expected — mGBA doesn't exit on Lua completion

    if output_file.exists():
        return output_file.read_text()
    return ""


def parse_scanner_output(raw: str) -> list[MemoryWatch]:
    """Parse scanner output into MemoryWatch objects."""
    addr_data = {}

    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line.startswith("0x"):
            continue

        parts = line.split(":")
        if len(parts) < 2:
            continue

        try:
            addr = int(parts[0].strip(), 16)
            rest = parts[1].strip()
            tokens = rest.split()
            old_val = int(tokens[0])
            new_val = int(tokens[2])
            frame = int(tokens[3].strip("(frame)"))
        except (ValueError, IndexError):
            continue

        if addr not in addr_data:
            addr_data[addr] = MemoryWatch(
                addr=addr, initial=old_val, current=new_val, changes=[]
            )
        addr_data[addr].changes.append((frame, old_val, new_val))
        addr_data[addr].current = new_val

    return list(addr_data.values())


def classify_watches(watches: list[MemoryWatch]) -> dict:
    """Classify discovered memory watches by type."""
    result = {
        "counters": [],
        "flags": [],
        "timers": [],
        "volatile": [],    # Changes every frame
        "stable": [],      # Changes rarely
    }

    for w in watches:
        if w.is_flag:
            result["flags"].append(w)
        elif w.is_counter:
            result["counters"].append(w)
        elif w.is_timer:
            result["timers"].append(w)
        elif w.change_count > 20:
            result["volatile"].append(w)
        else:
            result["stable"].append(w)

    return result


if __name__ == "__main__":
    # Demo: generate scanner Lua for Penta Dragon
    from re_discovery import PENTA_DRAGON_CONFIG

    addrs = {}
    for a in PENTA_DRAGON_CONFIG.addresses:
        addrs[a.name] = a.addr

    lua = generate_state_dumper_lua("state_dump.csv", addrs, frames=600)
    print("=== Generated State Dumper Lua ===")
    print(lua[:500])
    print("...")

    lua2 = generate_scanner_lua("scan_results.txt", frames=300)
    print("\n=== Generated Memory Scanner Lua ===")
    print(lua2[:500])
    print("...")
