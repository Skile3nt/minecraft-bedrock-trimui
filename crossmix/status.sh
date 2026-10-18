#!/bin/sh
# Best-effort native CrossMix status screen. Do not terminate other applications.
set -u
viewer="${MCPE_CARD_ROOT:?}/System/bin/sdl2imgshow"
resources="$MCPE_CARD_ROOT/System/resources"
if [ ! -x "$viewer" ] || [ ! -r "$resources/background.png" ] || [ ! -r "$resources/DejaVuSans.ttf" ]; then
    echo 'status_screen=unavailable (native viewer/resources missing)'
    exit 0
fi
"$viewer" -i "$resources/background.png" -f "$resources/DejaVuSans.ttf" \
    -s 30 -c '0,0,0' -t "$1" &
viewer_pid=$!
cleanup() {
    [ -n "$viewer_pid" ] || return 0
    kill "$viewer_pid" 2>/dev/null || :
    sleep 1
    kill -KILL "$viewer_pid" 2>/dev/null || :
    wait "$viewer_pid" 2>/dev/null || :
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM
sleep 6
if kill -0 "$viewer_pid" 2>/dev/null; then
    echo 'status_screen=display process alive (physical visibility unverified)'
else
    wait "$viewer_pid"
    echo "status_screen_exit=$?"
    viewer_pid=
fi
