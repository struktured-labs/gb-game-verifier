-- Sprite Counter — tracks visible OAM sprite count per frame
-- Useful for verifying enemy spawn rates match between OG and remake
-- Usage: mgba-qt rom.gbc --script lua/sprite_counter.lua

local frame = 0
local MAX_FRAMES = tonumber(os.getenv("VERIFY_MAX_FRAMES") or "1800")
local INPUT_FILE = os.getenv("VERIFY_INPUT_FILE") or "tmp/verify_inputs.csv"

local inp = {}
local fi = io.open(INPUT_FILE, "r")
if fi then
    for line in fi:lines() do
        local fr, keys = line:match("(%d+),(%d+)")
        if fr then inp[tonumber(fr)] = tonumber(keys) end
    end
    fi:close()
end

local csv = io.open("tmp/sprite_counts.csv", "w")
csv:write("frame,visible,nonzero\n")
csv:flush()

callbacks:add("frame", function()
    frame = frame + 1
    if inp[frame] then emu:setKeys(inp[frame]) end

    if frame % 30 == 0 then
        local visible = 0
        local nonzero = 0
        for s = 0, 39 do
            local y = emu:read8(0xFE00 + s * 4)
            local x = emu:read8(0xFE00 + s * 4 + 1)
            if y > 0 and y < 160 and x > 0 and x < 168 then
                visible = visible + 1
            end
            if y > 0 or x > 0 then
                nonzero = nonzero + 1
            end
        end
        csv:write(tostring(frame) .. "," .. tostring(visible) .. "," .. tostring(nonzero) .. "\n")
        csv:flush()
    end

    if frame >= MAX_FRAMES then
        csv:close()
        emu:quit()
    end
end)
