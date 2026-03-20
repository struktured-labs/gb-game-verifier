#!/bin/bash
# Quick comparison runner — generates inputs, runs both ROMs, diffs
# Usage: ./run_comparison.sh original.gb remake.gbc [frames] [interval]
set -e

OG="${1:?Usage: $0 original.gb remake.gbc [frames] [interval]}"
RM="${2:?}"
FRAMES="${3:-1800}"
INTERVAL="${4:-30}"
DIR="$(pwd)/tmp"

mkdir -p "$DIR/verify_og" "$DIR/verify_rm"

# Generate default inputs if not present
if [ ! -f "$DIR/verify_inputs.csv" ]; then
    cat > "$DIR/verify_inputs.csv" << 'EOF'
130,128
133,0
150,1
153,0
EOF
    echo "Generated default inputs (DOWN + A to start game)"
fi

# Create dump scripts
for side in og rm; do
    cat > "$DIR/dump_${side}.lua" << LUAEOF
local frame=0; local inp={}
local fi=io.open("$DIR/verify_inputs.csv","r")
if fi then for line in fi:lines() do local fr,keys=line:match("(%d+),(%d+)"); if fr then inp[tonumber(fr)]=tonumber(keys) end end fi:close() end
local csv=io.open("$DIR/verify_${side}/state.csv","w")
csv:write("frame,SCX,SCY,LCDC,room,form,boss,powerup,gameplay,stage,OAM0_Y,OAM0_X\\n"); csv:flush()
callbacks:add("frame",function() frame=frame+1; if inp[frame] then emu:setKeys(inp[frame]) end
if frame%${INTERVAL}==0 then
csv:write(tostring(frame)..","..tostring(emu:read8(0xFF43))..","..tostring(emu:read8(0xFF42))..","..tostring(emu:read8(0xFF40))..","..tostring(emu:read8(0xFFBD))..","..tostring(emu:read8(0xFFBE))..","..tostring(emu:read8(0xFFBF))..","..tostring(emu:read8(0xFFC0))..","..tostring(emu:read8(0xFFC1))..","..tostring(emu:read8(0xFFD0))..","..tostring(emu:read8(0xFE00))..","..tostring(emu:read8(0xFE01)).."\\n")
csv:flush()
end
if frame>=${FRAMES} then csv:close(); emu:quit() end end)
LUAEOF
done

TIMEOUT=$((FRAMES / 30 + 30))

# Run OG
echo "=== Running OG ($FRAMES frames) ==="
rm -f "$DIR/verify_og/state.csv"
Xvfb :97 -screen 0 640x480x24 &
XPID=$!
sleep 1
DISPLAY=:97 QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
timeout "$TIMEOUT" mgba-qt "$OG" --script "$DIR/dump_og.lua" -l 0 2>/dev/null || true
kill $XPID 2>/dev/null; wait $XPID 2>/dev/null; sleep 1

# Run Remake
echo "=== Running Remake ($FRAMES frames) ==="
rm -f "$DIR/verify_rm/state.csv"
Xvfb :97 -screen 0 640x480x24 &
XPID=$!
sleep 1
DISPLAY=:97 QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
timeout "$TIMEOUT" mgba-qt "$RM" --script "$DIR/dump_rm.lua" -l 0 2>/dev/null || true
kill $XPID 2>/dev/null; wait $XPID 2>/dev/null

echo ""
echo "=== Results ==="
OG_LINES=$(wc -l < "$DIR/verify_og/state.csv" 2>/dev/null || echo 0)
RM_LINES=$(wc -l < "$DIR/verify_rm/state.csv" 2>/dev/null || echo 0)
echo "OG: $OG_LINES lines, RM: $RM_LINES lines"

if [ "$OG_LINES" -gt 1 ] && [ "$RM_LINES" -gt 1 ]; then
    python3 "$(dirname "$0")/diff_report.py" "$DIR/verify_og/state.csv" "$DIR/verify_rm/state.csv"
else
    echo "ERROR: insufficient data captured"
fi
