-- Capture screenshots at specific DC81 values (scroll positions)
-- This syncs on game state, not frame count
local count = 0
local gf = 0
local booted = false
local captures = 0
local prev_dc81 = -1
local target_dc81 = {200, 196, 192, 188, 184, 180, 176, 172, 168, 164, 160, 156, 152, 148, 144, 140}
local target_idx = 1

callbacks:add("frame", function()
    count = count + 1
    -- Boot
    if count == 180 then emu:addKey(7) end
    if count == 185 then emu:clearKey(7) end
    if count == 193 then emu:addKey(0) end
    if count == 198 then emu:clearKey(0) end
    if count == 250 then emu:addKey(0) end
    if count == 255 then emu:clearKey(0) end
    if count == 300 then emu:addKey(3) end
    if count == 305 then emu:clearKey(3) end
    if count == 350 then emu:addKey(0) end
    if count == 355 then emu:clearKey(0) end

    if not booted and emu:read8(0xFFC1) == 1 then
        booted = true
    end
    if not booted then return end
    gf = gf + 1
    if gf <= 400 then return end

    -- Hold RIGHT to scroll
    emu:addKey(4)

    -- Capture at specific DC81 values (scroll positions)
    local dc81 = emu:read8(0xDC81)
    if target_idx <= #target_dc81 and dc81 <= target_dc81[target_idx] then
        emu:screenshot(string.format("sync_%03d_dc81_%03d.png", captures, dc81))
        captures = captures + 1
        target_idx = target_idx + 1
    end

    if captures >= #target_dc81 or gf > 2000 then
        emu:clearKey(4)
    end
end)
