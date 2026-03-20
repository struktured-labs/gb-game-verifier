-- Configurable GB state dumper for mGBA
-- Reads address list from a config file, dumps state every N frames
-- Config format: one address per line as "0xADDR,name"
--
-- Usage:
--   VERIFY_DUMP_DIR=tmp/dump VERIFY_CONFIG=configs/addrs.txt \
--   mgba-qt rom.gbc --script lua/configurable_dumper.lua

local DUMP_DIR = os.getenv("VERIFY_DUMP_DIR") or "tmp/verify_dump"
local CONFIG = os.getenv("VERIFY_CONFIG") or ""
local INTERVAL = tonumber(os.getenv("VERIFY_INTERVAL") or "30")
local MAX_FRAMES = tonumber(os.getenv("VERIFY_MAX_FRAMES") or "1800")
local INPUT_FILE = os.getenv("VERIFY_INPUT_FILE") or "tmp/verify_inputs.csv"

-- Parse address config
local addrs = {}
local names = {}
if CONFIG ~= "" then
    local f = io.open(CONFIG, "r")
    if f then
        for line in f:lines() do
            local addr, name = line:match("(0x%x+),(%S+)")
            if addr then
                table.insert(addrs, tonumber(addr))
                table.insert(names, name)
            end
        end
        f:close()
    end
end

-- Default addresses if no config
if #addrs == 0 then
    addrs = {0xFF43, 0xFF42, 0xFF40, 0xFFBD, 0xFFBE, 0xFFBF, 0xFFC0, 0xFFC1, 0xFFD0, 0xFE00, 0xFE01}
    names = {"SCX", "SCY", "LCDC", "room", "form", "boss", "powerup", "gameplay", "stage", "OAM0_Y", "OAM0_X"}
end

-- Load inputs
local inputs = {}
local fi = io.open(INPUT_FILE, "r")
if fi then
    for line in fi:lines() do
        local fr, keys = line:match("(%d+),(%d+)")
        if fr then inputs[tonumber(fr)] = tonumber(keys) end
    end
    fi:close()
end

-- Open CSV
local csv = io.open(DUMP_DIR .. "/state.csv", "w")
if not csv then return end
local hdr = "frame"
for _, n in ipairs(names) do hdr = hdr .. "," .. n end
csv:write(hdr .. "\n")
csv:flush()

local frame = 0
callbacks:add("frame", function()
    frame = frame + 1
    if inputs[frame] then emu:setKeys(inputs[frame]) end

    if frame % INTERVAL == 0 then
        local line = tostring(frame)
        for _, a in ipairs(addrs) do
            line = line .. "," .. tostring(emu:read8(a))
        end
        csv:write(line .. "\n")
        csv:flush()

        -- Screenshot every 10th dump
        if (frame / INTERVAL) % 10 == 0 then
            emu:screenshot(DUMP_DIR .. "/f" .. string.format("%05d", frame) .. ".png")
        end
    end

    if frame >= MAX_FRAMES then
        csv:close()
        emu:quit()
    end
end)
