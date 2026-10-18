#!/bin/bash
# Same session, libraries and Crusty attributes as Minecraft; no game loading.
set -euo pipefail
: "${GAMEDIR:?}"
export MCPE_GRAPHICS_PROBE=1
# Required session path only; the probe never opens this version's game files.
export MCVER_OVERRIDE=1.16.221.01-971622101-arm64
export MCPE_DATA_ROOT_OVERRIDE="$GAMEDIR/profiles/sdl-diagnostic"
test_dir=$(mktemp -d "$GAMEDIR/logs/sdl-test-XXXXXXXX")
mkdir "$test_dir/prior"
for name in crossmix-session-report.json crossmix-session.log crossmix-weston.log crossmix-client.log crossmix-runtime-inventory.json; do
    [ ! -f "$GAMEDIR/logs/$name" ] || cp "$GAMEDIR/logs/$name" "$test_dir/prior/$name"
done
printf '\n=== SDL session comparison %s ===\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
auto=1; explicit=1
for variant in auto explicit; do
    unset MCPE_SDL_PROBE_EXPLICIT_EGL
    [ "$variant" != explicit ] || export MCPE_SDL_PROBE_EXPLICIT_EGL=1
    # Preserve above, then prevent a setup failure from reusing an earlier report.
    printf '{}\n' >"$GAMEDIR/logs/crossmix-session-report.json"
    printf '{}\n' >"$GAMEDIR/logs/crossmix-runtime-inventory.json"
    status=0
    # Time bound belongs only to this diagnostic invocation.
    sh "$GAMEDIR/crossmix/bin/bash" "$GAMEDIR/crossmix/session.sh" 20 || status=$?
    printf 'sdl_test_variant=%s exit_code=%s\n' "$variant" "$status"
    mkdir "$test_dir/$variant"
    for name in crossmix-session-report.json crossmix-session.log crossmix-weston.log crossmix-client.log crossmix-runtime-inventory.json; do
        [ ! -f "$GAMEDIR/logs/$name" ] || cp "$GAMEDIR/logs/$name" "$test_dir/$variant/$name"
    done
    printf '%s\n' "$status" >"$test_dir/$variant/exit-code.txt"
    if [ "$variant" = auto ]; then auto=$status; else explicit=$status; fi
done
python3 "$GAMEDIR/crossmix/sdl_test_report.py" "$test_dir" "$GAMEDIR/logs/crossmix-sdl-test.json"
# Both codes remain available in the JSON even when one variant succeeds.
[ "$auto" -eq 0 ] && [ "$explicit" -eq 0 ]
