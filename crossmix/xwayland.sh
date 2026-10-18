#!/bin/sh
set -eu
# The packaged Xwayland has no glamor support. Crusty presents via SDL/PowerVR.
cd "${MCPE_SESSION_DIR:?}"
printf '%s\n' "$$" >"$MCPE_SESSION_DIR/xwayland.pid"
export MCPE_NATIVE_LIBRARY_PREFIX="$GAMEDIR/crossmix/runtime/weston/lib_aarch64/extra_fakeglx"
unset MCPE_NATIVE_PRELOAD MCPE_NATIVE_AUDIT
exec "$GAMEDIR/crossmix/native-run.sh" "$GAMEDIR/crossmix/runtime/weston/bin/Xwayland" "$@" -shm -nolisten tcp
