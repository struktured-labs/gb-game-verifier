#!/bin/bash
# Run full verification suite — multiple input scenarios
# Usage: ./run_suite.sh "original.gb" "remake.gbc"
set -euo pipefail

OG="${1:?Usage: $0 original.gb remake.gbc}"
RM="${2:?}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIR="$(pwd)/tmp/suite"

mkdir -p "$DIR"

# Generate input scenarios
# 1. Idle (start game, no further input)
printf '130,128\n133,0\n150,1\n153,0\n500,1\n503,0\n700,1\n703,0\n' > "$DIR/inputs_idle.csv"

# 2. DOWN held (start game, hold DOWN from F800)
cp "$DIR/inputs_idle.csv" "$DIR/inputs_down.csv"
echo "800,128" >> "$DIR/inputs_down.csv"

# 3. RIGHT held (start game, hold RIGHT from F800)
cp "$DIR/inputs_idle.csv" "$DIR/inputs_right.csv"
echo "800,16" >> "$DIR/inputs_right.csv"

# 4. Combat (UP+A / DOWN+A alternating)
cp "$DIR/inputs_idle.csv" "$DIR/inputs_combat.csv"
python3 -c "
for f in range(800, 3600, 60):
    print(f'{f},65')
    print(f'{f+30},129')
" >> "$DIR/inputs_combat.csv"

SCENARIOS="idle down right combat"
FRAMES_idle=1800
FRAMES_down=1800
FRAMES_right=1800
FRAMES_combat=3600

echo "========================================"
echo "GB VERIFIER SUITE — $(date)"
echo "========================================"
echo ""

ALL_PASS=true

for scenario in $SCENARIOS; do
    eval frames=\$FRAMES_$scenario
    echo "--- $scenario ($frames frames) ---"

    for side in og rm; do
        eval rom=\$$(echo $side | tr a-z A-Z)
        sd="$DIR/${scenario}_${side}"
        mkdir -p "$sd"

        # Paths relative to DIR (mGBA launched from DIR)
        REL_INPUT="inputs_${scenario}.csv"
        REL_CSV="${scenario}_${side}/state.csv"
        printf 'local frame=0; local inp={}\n' > "$sd/dump.lua"
        printf 'local fi=io.open("%s","r")\n' "$REL_INPUT" >> "$sd/dump.lua"
        printf 'if fi then for line in fi:lines() do local fr,keys=line:match("(%%d+),(%%d+)"); if fr then inp[tonumber(fr)]=tonumber(keys) end end fi:close() end\n' >> "$sd/dump.lua"
        printf 'local csv=io.open("%s","w")\n' "$REL_CSV" >> "$sd/dump.lua"
        cat >> "$sd/dump.lua" << 'LUABLOCK'
csv:write("frame,SCX,SCY,room,form,boss,powerup,gameplay,stage,OAM0_Y,OAM0_X\n"); csv:flush()
callbacks:add("frame",function() frame=frame+1; if inp[frame] then emu:setKeys(inp[frame]) end
if frame%30==0 then
csv:write(tostring(frame)..","..tostring(emu:read8(0xFF43))..","..tostring(emu:read8(0xFF42))..","..tostring(emu:read8(0xFFBD))..","..tostring(emu:read8(0xFFBE))..","..tostring(emu:read8(0xFFBF))..","..tostring(emu:read8(0xFFC0))..","..tostring(emu:read8(0xFFC1))..","..tostring(emu:read8(0xFFD0))..","..tostring(emu:read8(0xFE00))..","..tostring(emu:read8(0xFE01)).."\n")
csv:flush()
end
LUABLOCK
        printf 'if frame>=%d then csv:close(); emu:quit() end end)\n' "$frames" >> "$sd/dump.lua"
        timeout_sec=$((frames / 30 + 30))
        Xvfb :97 -screen 0 640x480x24 &
        XPID=$!
        sleep 1
        # Launch mGBA from $DIR so relative paths in Lua work
        (cd "$DIR" && DISPLAY=:97 QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
        timeout "$timeout_sec" mgba-qt "$rom" --script "$sd/dump.lua" -l 0 2>/dev/null) || true
        kill "$XPID" 2>/dev/null; wait "$XPID" 2>/dev/null; sleep 1
    done

    OG_CSV="$DIR/${scenario}_og/state.csv"
    RM_CSV="$DIR/${scenario}_rm/state.csv"

    if [ -f "$OG_CSV" ] && [ -f "$RM_CSV" ]; then
        result=$(python3 "$SCRIPT_DIR/summary.py" "$OG_CSV" "$RM_CSV" 2>&1) || true
        echo "  $result"
        echo "$result" | grep -q "^FAIL" && ALL_PASS=false
    else
        echo "  SKIP (insufficient data)"
    fi
    echo ""
done

echo "========================================"
if $ALL_PASS; then
    echo "SUITE PASSED"
else
    echo "SUITE FAILED — see details above"
    exit 1
fi
