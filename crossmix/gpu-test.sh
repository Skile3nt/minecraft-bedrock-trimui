#!/bin/sh
set -eu
exec >>"${GAMEDIR:?}/logs/crossmix-graphics.log" 2>&1
stage=resolve-libraries
finish() { result=$?; echo "graphics_stage=$stage exit_code=$result"; }
trap finish 0
printf '\n=== GPU test %s ===\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
resolved=$(python3 "$GAMEDIR/crossmix/probe.py" --native-libraries)
eval "$resolved"
export CRUSTY_LIBSDL CRUSTY_LIBEGL CRUSTY_LIBGLES
printf 'SDL=%s\nEGL=%s\nGLES=%s\n' "$CRUSTY_LIBSDL" "$CRUSTY_LIBEGL" "$CRUSTY_LIBGLES"
export SDL_VIDEODRIVER=mali SDL_VIDEO_EGL_DRIVER="$CRUSTY_LIBEGL"
export SDL_VIDEO_GL_DRIVER="$CRUSTY_LIBGLES"
# The private loader is scoped to the probe; SDL subprocesses use firmware libs.
export MCPE_NATIVE_CHILD_LIBRARY_PATH="$MCPE_CARD_ROOT/System/lib:/usr/trimui/lib:/usr/lib:/lib"
printf 'SDL_VIDEO_GL_DRIVER=%s\nhelper_libraries=%s\n' "$SDL_VIDEO_GL_DRIVER" "$MCPE_NATIVE_CHILD_LIBRARY_PATH"
export MCPE_NATIVE_PRELOAD="$CRUSTY_LIBGLES"
stage=gles-context
sh "$GAMEDIR/crossmix/native-run.sh" "$GAMEDIR/crossmix/graphics-probe"
