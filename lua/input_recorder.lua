-- Input Recorder — records human inputs for replay
-- Captures joypad state every frame, saves to CSV
-- Usage: mgba-qt rom.gbc --script lua/input_recorder.lua
-- Then play the game normally. Press SELECT+START to stop recording.

local frame = 0
local recording = true
local output_file = os.getenv("RECORD_FILE") or "tmp/recorded_inputs.csv"
local MAX_FRAMES = tonumber(os.getenv("RECORD_MAX") or "18000")  -- 5 minutes

local csv = io.open(output_file, "w")
if not csv then
    console:log("ERROR: cannot open " .. output_file)
    return
end

local prev_keys = 0
local events = 0

callbacks:add("frame", function()
    frame = frame + 1

    if not recording then return end

    local keys = emu:getKeys and emu:getKeys() or 0

    -- Only log when keys change (reduces file size)
    if keys ~= prev_keys then
        csv:write(tostring(frame) .. "," .. tostring(keys) .. "\n")
        csv:flush()
        events = events + 1
        prev_keys = keys
    end

    -- Stop on SELECT+START (0x04 + 0x08 = 0x0C)
    if keys == 0x0C then
        recording = false
        csv:close()
        console:log("Recording stopped: " .. events .. " events in " .. frame .. " frames")
        console:log("Saved to: " .. output_file)
    end

    -- Auto-stop at max frames
    if frame >= MAX_FRAMES then
        recording = false
        csv:close()
        console:log("Recording auto-stopped at " .. frame .. " frames (" .. events .. " events)")
        emu:quit()
    end
end)

console:log("Recording inputs to " .. output_file)
console:log("Press SELECT+START to stop recording")
