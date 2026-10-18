#!/bin/sh
# Keep the new libc out of /bin/sh, Bash, Python and the firmware environment.
set -eu
runtime="${GAMEDIR:?}/crossmix/runtime"
loader="$runtime/debian/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1"
[ -x "$loader" ] || { echo "Private ARM64 loader missing: $loader" >&2; exit 1; }
libpath="$runtime/debian/lib/aarch64-linux-gnu:$runtime/debian/usr/lib/aarch64-linux-gnu"
libpath="$libpath:$GAMEDIR/libs.aarch64:$runtime/weston/lib_aarch64"
libpath="$libpath:${MCPE_CARD_ROOT:?}/System/lib:/usr/trimui/lib:/usr/lib:/lib"
libpath="${MCPE_NATIVE_LIBRARY_PREFIX:+$MCPE_NATIVE_LIBRARY_PREFIX:}$libpath"
unset LD_PRELOAD
# Westonpack xwayland.so calls strlen(getenv("LD_LIBRARY_PATH")) without a NULL check.
# Keep a nonempty harmless value; all private paths remain loader arguments.
# Optional firmware-only paths let native helpers (e.g. SDL setterm) run.
# Never put the private glibc directory in this inherited environment.
export LD_LIBRARY_PATH="${MCPE_NATIVE_CHILD_LIBRARY_PATH:-/nonexistent}"
# Audit stays on this private-loader invocation, never in firmware subprocesses.
if [ -n "${MCPE_NATIVE_PRELOAD:-}" ]; then
    set -- --preload "$MCPE_NATIVE_PRELOAD" "$@"
fi
if [ -n "${MCPE_NATIVE_AUDIT:-}" ]; then
    set -- --audit "$MCPE_NATIVE_AUDIT" "$@"
fi
exec "$loader" --inhibit-cache --library-path "$libpath" "$@"
