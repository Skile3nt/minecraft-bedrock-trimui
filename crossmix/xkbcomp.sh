#!/bin/sh
# Xwayland invokes bin/xkbcomp relative to its private working directory.
set -eu
unset MCPE_NATIVE_PRELOAD
exec "$GAMEDIR/crossmix/native-run.sh" "$GAMEDIR/crossmix/runtime/weston/bin/xkbcomp" "$@"
