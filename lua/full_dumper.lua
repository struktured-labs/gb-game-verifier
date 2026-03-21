-- Full state dumper — memory state + sprite count + OAM positions
-- Combines state_dumper + sprite_counter into one pass
-- Usage: mgba-qt rom.gbc --script lua/full_dumper.lua

local frame = 0
local INTERVAL = tonumber(os.getenv("VERIFY_INTERVAL") or "30")
local MAX_FRAMES = tonumber(os.getenv("VERIFY_MAX_FRAMES") or "1800")
local DUMP_DIR = os.getenv("VERIFY_DUMP_DIR") or "tmp/verify_dump"
local INPUT_FILE = os.getenv("VERIFY_INPUT_FILE") or "tmp/verify_inputs.csv"

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
csv:write("frame,SCX,SCY,LCDC,room,form,boss,powerup,gameplay,stage,OAM0_Y,OAM0_X,sprites_visible\n")
csv:flush()

callbacks:add("frame", function()
    frame = frame + 1
    if inputs[frame] then emu:setKeys(inputs[frame]) end

    if frame % INTERVAL == 0 then
        -- Count visible sprites
        local vis = 0
        for s = 0, 39 do
            local y = emu:read8(0xFE00 + s * 4)
            local x = emu:read8(0xFE00 + s * 4 + 1)
            if y > 0 and y < 160 and x > 0 and x < 168 then
                vis = vis + 1
            end
        end

        -- Write all state
        csv:write(tostring(frame) .. ","
            .. tostring(emu:read8(0xFF43)) .. ","
            .. tostring(emu:read8(0xFF42)) .. ","
            .. tostring(emu:read8(0xFF40)) .. ","
            .. tostring(emu:read8(0xFFBD)) .. ","
            .. tostring(emu:read8(0xFFBE)) .. ","
            .. tostring(emu:read8(0xFFBF)) .. ","
            .. tostring(emu:read8(0xFFC0)) .. ","
            .. tostring(emu:read8(0xFFC1)) .. ","
            .. tostring(emu:read8(0xFFD0)) .. ","
            .. tostring(emu:read8(0xFE00)) .. ","
            .. tostring(emu:read8(0xFE01)) .. ","
            .. tostring(vis) .. "\n")
        csv:flush()
    end

    if frame >= MAX_FRAMES then
        csv:close()
        emu:quit()
    end
end)
