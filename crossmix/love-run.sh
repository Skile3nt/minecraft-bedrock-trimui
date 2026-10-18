#!/bin/sh
set -eu
love_root="${controlfolder:?}/runtimes/love_11.5"
[ -x "$love_root/love.aarch64" ] || { echo 'CrossMix LOVE 11.5 runtime missing.' >&2; exit 1; }
export LD_LIBRARY_PATH="$love_root/libs.aarch64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export SDL_VIDEODRIVER=mali
exec "$love_root/love.aarch64" "$@"
