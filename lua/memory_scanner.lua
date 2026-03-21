-- Memory Scanner — discovers which addresses change during gameplay
-- Scans HRAM (FF80-FFFE) and key WRAM ranges, logs any that change
-- Usage: mgba-qt rom.gbc --script lua/memory_scanner.lua

local frame = 0
local SCAN_START = 300  -- Start scanning after boot
local SCAN_END = 1800   -- Stop after 30 seconds
local DUMP_INTERVAL = 60

-- Ranges to scan
local ranges = {
    {0xFF40, 0xFF4F, "LCD regs"},
    {0xFF80, 0xFFFE, "HRAM"},
    {0xC000, 0xC0FF, "WRAM low"},
    {0xD000, 0xD0FF, "WRAM D0"},
    {0xDC00, 0xDCFF, "WRAM DC"},
    {0xFE00, 0xFE9F, "OAM"},
}

-- Track initial values
local initial = {}
local changed = {}
local scanned = false

callbacks:add("frame", function()
    frame = frame + 1

    -- Capture initial state
    if frame == SCAN_START and not scanned then
        for _, r in ipairs(ranges) do
            for addr = r[1], r[2] do
                initial[addr] = emu:read8(addr)
            end
        end
        scanned = true
    end

    -- Check for changes periodically
    if scanned and frame % DUMP_INTERVAL == 0 and frame <= SCAN_END then
        for _, r in ipairs(ranges) do
            for addr = r[1], r[2] do
                local val = emu:read8(addr)
                if val ~= initial[addr] and not changed[addr] then
                    changed[addr] = {
                        initial = initial[addr],
                        new = val,
                        frame = frame,
                        range = r[3]
                    }
                end
            end
        end
    end

    -- Write results
    if frame == SCAN_END then
        local f = io.open("tmp/memory_scan.txt", "w")
        if f then
            f:write("=== Memory Scanner Results ===\n")
            f:write("Scanned " .. tostring(SCAN_END - SCAN_START) .. " frames\n\n")

            -- Sort by address
            local addrs = {}
            for addr, _ in pairs(changed) do
                table.insert(addrs, addr)
            end
            table.sort(addrs)

            f:write("Addresses that changed during gameplay:\n")
            for _, addr in ipairs(addrs) do
                local c = changed[addr]
                f:write(string.format(
                    "  0x%04X: %d -> %d (frame %d) [%s]\n",
                    addr, c.initial, c.new, c.frame, c.range
                ))
            end
            f:write("\nTotal: " .. #addrs .. " addresses changed\n")
            f:close()
        end
        console:log("Memory scan complete: " .. #addrs .. " addresses changed")
        emu:quit()
    end
end)
