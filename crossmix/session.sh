#!/bin/bash
# A private headless Weston/Xwayland session. No mount, global service or DRM mknod.
set -Eeuo pipefail
: "${GAMEDIR:?}" "${MCVER_OVERRIDE:?}"
mkdir -p "$GAMEDIR/logs"
SESSION_LOG="$GAMEDIR/logs/crossmix-session.log"
stage=prepare
: >"$SESSION_LOG"
: >"$GAMEDIR/logs/crossmix-weston.log"
# Avoid presenting stale client output if this attempt fails before spawning it.
printf 'client_not_started: waiting for session setup\n' >"$GAMEDIR/logs/crossmix-client.log"
# The upstream tee may close its pipe during external termination. The file
# remains authoritative; EPIPE must never replace the original process status.
log() { printf '%s\n' "$*" >>"$SESSION_LOG"; }
: >"$GAMEDIR/logs/crossmix-performance.jsonl"
: >"$GAMEDIR/logs/crossmix-input.log"
printf '{"state":"running","pid":%s,"exit_code":null}\n' "$$" >"$GAMEDIR/logs/crossmix-session-report.json"
: >"$GAMEDIR/logs/crossmix-failure.txt"
timepoint() {
    local uptime rest
    read -r uptime rest </proc/uptime
    printf '{"uptime":%s,"event":"%s"}\n' "$uptime" "$1" >>"$GAMEDIR/logs/crossmix-performance.jsonl"
}
timepoint session_prepare
# Timestamp written by the menu at Play, rather than when Ports was opened.
if [ "${MCPE_GRAPHICS_PROBE:-0}" != 1 ] && [ -r "$GAMEDIR/config/play-uptime.txt" ]; then
    boot_uptime=${MCPE_BOOT_UPTIME:-0}
    read -r current_uptime rest </proc/uptime
    read -r play_uptime <"$GAMEDIR/config/play-uptime.txt" || true
    if [[ "${play_uptime:-}" =~ ^[0-9]+\.[0-9]+$ ]] &&
       [[ "$boot_uptime" =~ ^[0-9]+(\.[0-9]+)?$ ]] &&
       [ "${play_uptime%%.*}" -ge "${boot_uptime%%.*}" ] &&
       [ "${play_uptime%%.*}" -le "${current_uptime%%.*}" ]; then
        printf '{"uptime":%s,"event":"play_selected"}\n' "$play_uptime" >>"$GAMEDIR/logs/crossmix-performance.jsonl"
    fi
fi
case "${MCPE_BOOT_UPTIME:-}" in
    ''|*[!0-9.]*) ;; *)
        printf '{"uptime":%s,"event":"entry_bootstrap"}\n' "$MCPE_BOOT_UPTIME" >>"$GAMEDIR/logs/crossmix-performance.jsonl" ;;
esac
log "session_start=$(date -u '+%Y-%m-%dT%H:%M:%SZ') pid=$$ version=$MCVER_OVERRIDE"
trap 'result=$?; log "session_error stage=$stage line=$LINENO exit_code=$result"; exit "$result"' ERR
W="$GAMEDIR/crossmix/runtime/weston"
RUN="$GAMEDIR/crossmix/native-run.sh"
CLIENT="$GAMEDIR/bin/mcpelauncher-client"
client_role=mcpelauncher-client
if [ "${MCPE_GRAPHICS_PROBE:-0}" = 1 ]; then
    CLIENT="$GAMEDIR/crossmix/sdl-session-probe"
    client_role=sdl-session-probe
else
    # A/B changes are isolated to the diagnostic entry, never the actual game.
    unset MCPE_SDL_PROBE_EXPLICIT_EGL
fi
GAME="$GAMEDIR/versions/$MCVER_OVERRIDE"
DATA_ROOT="${MCPE_DATA_ROOT_OVERRIDE:-$GAMEDIR/profiles/default}"
SESSION=$(mktemp -d /tmp/mcpe-crossmix.XXXXXX)
chmod 700 "$SESSION"
FRAME_METRICS_TMP="$SESSION/crossmix-frames.jsonl"
FRAME_METRICS_FINAL="$GAMEDIR/logs/crossmix-frames.jsonl"
weston_pid= client_pid= watcher_pid= metrics_pid= profile_prepared=0
stop_child() {
    local p="$1" role="${2:-helper}"
    [ -n "$p" ] || return 0
    timepoint "${role}_cleanup_begin"
    kill -TERM "$p" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "$p" 2>/dev/null || break
        sleep 0.1
    done
    if kill -0 "$p" 2>/dev/null; then
        log "cleanup_forced role=$role pid=$p signal=KILL"
        kill -KILL "$p" 2>/dev/null || true
    fi
    wait "$p" 2>/dev/null || true
    timepoint "${role}_cleanup_end"
}
cleanup() {
    stop_child "$watcher_pid" watcher
    stop_child "$metrics_pid" metrics
    stop_child "$client_pid" client
    stop_child "$weston_pid" weston
    # Frame batches are collected on the render thread. Keep their periodic
    # writes off the microSD during gameplay; persist once after the client is
    # gone so reports still archive this session's data.
    if [ -f "$FRAME_METRICS_TMP" ]; then
        local frame_copy="$FRAME_METRICS_FINAL.tmp.$$"
        if cp -- "$FRAME_METRICS_TMP" "$frame_copy" &&
           mv -f -- "$frame_copy" "$FRAME_METRICS_FINAL"; then
            log "frame_metrics_persisted=1 sink=tmpfs destination=$FRAME_METRICS_FINAL"
        else
            rm -f -- "$frame_copy"
            log 'frame_metrics_persisted=0 sink=tmpfs (copy failed; prior log retained)'
        fi
    fi
    # Only the directory allocated by this invocation is removed.
    rm -rf -- "$SESSION"
}
finish_session() {
    local result=$?
    trap - EXIT ERR
    log "session_finished stage=$stage exit_code=$result"
    # Preserve the analysis boundary while still measuring cleanup. Any messages
    # emitted by terminated children after this marker are teardown observations.
    printf '\nCrossMix cleanup_begin\n' >>"$GAMEDIR/logs/crossmix-client.log"
    printf '\nCrossMix cleanup_begin\n' >>"$GAMEDIR/logs/crossmix-weston.log"
    log 'cleanup=stopping owned client/Weston; subsequent TERM/Broken pipe are cleanup events'
    cleanup
    if [ "${MCPE_PERF_PROFILE_ACTIVE:-ORIGINAL}" = PERFORMANCE ]; then
        local fps_option="$DATA_ROOT/mcpelauncher/games/com.mojang/minecraftpe/options.txt"
        if [ -r "$fps_option" ]; then
            local fps_readback
            fps_readback=$(sed -n 's/^gfx_max_framerate://p' "$fps_option" | head -n 1)
            log "performance_fps_cap_option_at_exit=${fps_readback:-missing}"
        fi
    fi
    if [ "$profile_prepared" = 1 ]; then
        timepoint profile_restore_begin
        python3 "$GAMEDIR/crossmix/performance_profiles.py" restore >>"$SESSION_LOG" 2>&1 || log 'profile_restore_failed=1 (journal/backups retained; next launch retries)'
        timepoint profile_restore_end
    fi
    timepoint session_cleanup_finished
    # Reporting has a real file sink, including wrapper stderr; no dependency
    # on the upstream console pipe. Cleanup is explicitly marked in the logs.
    python3 "$GAMEDIR/crossmix/session_report.py" "$GAMEDIR" "$result" "$stage" >>"$SESSION_LOG" 2>&1 || log 'session_report_failed=1 (original logs retained)'
    exit "$result"
}
trap finish_session EXIT
trap 'exit 130' INT
trap 'log "session_signal=TERM stage=$stage"; exit 143' TERM
trap 'log "session_signal=HUP stage=$stage"; exit 129' HUP
stage=x11-socket-directory
# Weston binds /tmp/.X11-unix/Xn before spawning Xwayland. CrossMix does not
# create its parent at boot. Preserve existing directories, sockets and locks.
python3 "$GAMEDIR/crossmix/prepare_x11.py" >>"$SESSION_LOG" 2>&1
export MCPE_SESSION_DIR="$SESSION" XDG_RUNTIME_DIR="$SESSION"
export XKB_CONFIG_ROOT="$W/share/xkb"
export WESTON_DATA_DIR="$W/data" WESTON_LIBEXEC_DIR="$W/libexec"
mods="$W/lib_aarch64"
export WESTON_MODULE_MAP="headless-backend.so=$mods/libweston-14/headless-backend.so;kiosk-shell.so=$mods/weston/kiosk-shell.so;xwayland.so=$mods/libweston-14/xwayland.so;"
export WESTON_NO_HEADLESS_INPUT=1 WESTON_KIOSK_NO_RESIZE=1
export LIBSEAT_BACKEND=builtin SEATD_VTBOUND=0
export WESTON_HEADLESS_WIDTH="${MCPE_DISPLAY_WIDTH:-1280}"
export WESTON_HEADLESS_HEIGHT="${MCPE_DISPLAY_HEIGHT:-720}"
# Its patched spawn callback concatenates this with LD_LIBRARY_PATH.
# The shell wrapper must start with firmware libc; it selects private libs itself.
export XWAYLAND_LD_LIBRARY_PATH=/nonexistent
# This Xwayland has relative XKB paths and duplicates share/xkb on readback.
# All generated maps and compatibility links live only in this invocation.
mkdir -p "$SESSION/bin" "$SESSION/share/xkb/compiled"
ln -s "$GAMEDIR/crossmix/xkbcomp.sh" "$SESSION/bin/xkbcomp"
for section in "$W"/share/xkb/*; do
    [ -e "$section" ] || continue
    ln -s "$section" "$SESSION/share/xkb/$(basename "$section")"
done
ln -s .. "$SESSION/share/xkb/share"
cat >"$SESSION/weston.ini" <<EOF
[core]
xwayland=true
idle-time=0
[input-method]
path=
[xwayland]
path=$GAMEDIR/crossmix/xwayland.sh
EOF
LOG="$GAMEDIR/logs/crossmix-weston.log"
# Patched Westonpack has relative paths in addition to its module map.
cd "$W"
stage=weston-start
timepoint weston_start
log "process=weston executable=$W/wp_weston log=$LOG"
"$RUN" "$W/wp_weston" -c "$SESSION/weston.ini" -B headless --renderer=noop \
    --shell=kiosk-shell.so -i0 -Smcpe-wayland --xwayland >"$LOG" 2>&1 &
weston_pid=$!
printf '%s\n' "$weston_pid" >"$SESSION/weston.pid"
xsock=
for _ in {1..150}; do
    if ! kill -0 "$weston_pid" 2>/dev/null; then
        weston_status=0
        wait "$weston_pid" || weston_status=$?
        weston_pid=
        log "process=weston exit_code=$weston_status client_started=0"
        cat "$LOG"
        exit 1
    fi
    xsock=$(sed -n 's/.*xserver listening on display \(:[0-9][0-9]*\).*/\1/p' "$LOG" | head -1)
    if [ -S "$SESSION/mcpe-wayland" ] && [ -n "$xsock" ]; then break; fi
    sleep 0.1
 done
[ -n "$xsock" ] && [ -S "$SESSION/mcpe-wayland" ] || { log 'process=weston startup_timeout=15s client_started=0'; cat "$LOG"; exit 1; }
log "stage=weston-listening display=$xsock pid=$weston_pid (Xwayland starts on demand)"
timepoint weston_listening
export DISPLAY="$xsock" WAYLAND_DISPLAY=mcpe-wayland
log "DISPLAY=$DISPLAY WAYLAND_DISPLAY=$WAYLAND_DISPLAY XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
log "wayland_socket=$SESSION/mcpe-wayland x11_socket=/tmp/.X11-unix/X${DISPLAY#:}"
export CRUSTY_WLMODE=0 CRUSTY_WLDISP=mcpe-wayland CRUSTY_SHOW_CURSOR=0
# Resolve actual firmware libraries, never our libEGL shim.
stage=native-libraries
native_libraries=$(python3 "$GAMEDIR/crossmix/probe.py" --native-libraries)
eval "$native_libraries"
: "${CRUSTY_LIBSDL:?}" "${CRUSTY_LIBEGL:?}" "${CRUSTY_LIBGLES:?}"
log "native_sdl=$CRUSTY_LIBSDL native_egl=$CRUSTY_LIBEGL native_gles=$CRUSTY_LIBGLES"
export CRUSTY_LIBSDL CRUSTY_LIBEGL CRUSTY_LIBGLES
python3 "$GAMEDIR/crossmix/runtime_inventory.py" "$GAMEDIR/logs/crossmix-runtime-inventory.json" >>"$SESSION_LOG" 2>&1 || log 'runtime_inventory_failed=1'
mkdir "$SESSION/native-gl"
ln -s "$CRUSTY_LIBGLES" "$SESSION/native-gl/libGLESv2.so"
ln -s "$CRUSTY_LIBGLES" "$SESSION/native-gl/libGLESv2.so.2"
# The FAT package dereferences Westonpack's symlinks into separate ELF files.
# Loading both libcrusty.so and a copied libEGL.so.1 makes Crusty's RTLD_NEXT
# dlopen resolve to another Crusty hook instead of libc. SDL is then redirected
# to libCRU.so despite correct backend classification. Recreate only our four
# aliases on session tmpfs so every facade resolves to the ONE preloaded inode.
mkdir "$SESSION/crusty"
for name in libEGL.so libEGL.so.1 libCRU.so libCRU.so.1; do
    ln -s "$W/lib_aarch64/graphics/crusty_x11egl/libcrusty.so" "$SESSION/crusty/$name"
done
log "crusty_aliases=single-object directory=$SESSION/crusty"
export SDL_VIDEODRIVER=mali SDL_VIDEO_EGL_DRIVER="$CRUSTY_LIBEGL"
export SDL_VIDEO_GL_DRIVER="$CRUSTY_LIBGLES"
export MCPE_NATIVE_CHILD_LIBRARY_PATH="$MCPE_CARD_ROOT/System/lib:/usr/trimui/lib:/usr/lib:/lib"
export SDL_AUDIODRIVER="${MCPE_SDL_AUDIODRIVER:-alsa}"
export SDL_AUDIO_DRIVER="$SDL_AUDIODRIVER"
export ALSA_CONFIG_PATH="${ALSA_CONFIG_PATH:-$GAMEDIR/crossmix/runtime/debian/usr/share/alsa/alsa.conf}"
export ALSA_CONFIG_DIR="$GAMEDIR/crossmix/runtime/debian/usr/share/alsa"
export XDG_DATA_HOME="$DATA_ROOT" MCPELAUNCHER_DATA_DIR="$DATA_ROOT/mcpelauncher"
mkdir -p "$MCPELAUNCHER_DATA_DIR/games/com.mojang"
export MCPE_RENDER_WIDTH="$WESTON_HEADLESS_WIDTH" MCPE_RENDER_HEIGHT="$WESTON_HEADLESS_HEIGHT"
if [ "$client_role" = mcpelauncher-client ] && [ -r "$GAMEDIR/crossmix/performance_profiles.py" ]; then
    stage=performance-profile
    profile_prepared=1
    timepoint profile_prepare_begin
    profile_environment=$(python3 "$GAMEDIR/crossmix/performance_profiles.py" prepare)
    timepoint profile_prepare_end
    eval "$profile_environment"
    log "performance_profile=${MCPE_PERF_PROFILE_ACTIVE:-ORIGINAL} render_requested=${MCPE_RENDER_WIDTH}x${MCPE_RENDER_HEIGHT} physical_panel=${WESTON_HEADLESS_WIDTH}x${WESTON_HEADLESS_HEIGHT}"
    if [ "${MCPE_PERF_PROFILE_ACTIVE:-ORIGINAL}" = PERFORMANCE ]; then
        log "performance_fps_cap_requested=${MCPE_PERF_FPS_CAP_ACTIVE:-unchanged} option=gfx_max_framerate scope=temporary-profile"
    fi
fi
export MCPE_NATIVE_LIBRARY_PREFIX="$SESSION/crusty:$SESSION/native-gl:$GAME/lib/arm64-v8a"
export MCPE_NATIVE_PRELOAD="$GAMEDIR/bin/crusty-context-v1.so:$GAMEDIR/crossmix/isolate-crusty.so:$GAMEDIR/crossmix/sdl-trace.so:$W/lib_aarch64/graphics/crusty_x11egl/libcrusty.so:$CRUSTY_LIBGLES"
if [ "${MCPE_PERF_PROFILE_ACTIVE:-ORIGINAL}" != ORIGINAL ] && [ -r "$GAMEDIR/crossmix/particle-audit.so" ]; then
    export MCPE_PARTICLE_ROOT="$GAMEDIR/versions/$MCVER_OVERRIDE/assets"
    export MCPE_PARTICLE_LOG="$GAMEDIR/logs/crossmix-particle-audit.log"
    : >"$MCPE_PARTICLE_LOG"
    export MCPE_NATIVE_PRELOAD="$GAMEDIR/crossmix/particle-audit.so:$MCPE_NATIVE_PRELOAD"
fi
if [ "$client_role" = mcpelauncher-client ]; then
    export MCPE_INPUT_LOG="$GAMEDIR/logs/crossmix-input.log"
    export MCPE_NATIVE_PRELOAD="$GAMEDIR/crossmix/input-bridge.so:$MCPE_NATIVE_PRELOAD"
fi
export MCPE_TIMING_LOG="$GAMEDIR/logs/crossmix-performance.jsonl"
# Binding auditor returns original function addresses without changing routing.
export MCPE_NATIVE_AUDIT="$GAMEDIR/crossmix/egl-bind-audit.so"
export GAMEWINDOW_EGLUT_CRUSTY_CONTEXT=1 GAMEWINDOW_EGLUT_FORCE_FOCUS=1
export OPENSSL_armcap=0 MALLOC_CHECK_=0
export MCPE_BENCH_FILE="$FRAME_METRICS_TMP"
: >"$MCPE_BENCH_FILE"
log "frame_metrics_sink=tmpfs path=$MCPE_BENCH_FILE persist=after-client-exit"
# Keep Weston/panel native. Crusty's existing resolution switch requests the
# application's actual SDL surface; a native EGL probe gates this before game.
if [ "${MCPE_PERF_PROFILE_ACTIVE:-ORIGINAL}" = PERFORMANCE ]; then
    export CRUSTY_RESOLUTION="${MCPE_RENDER_WIDTH}x${MCPE_RENDER_HEIGHT}"
    resolution_probe=0
    "$RUN" "$GAMEDIR/crossmix/sdl-session-probe" --size-check-only "$MCPE_RENDER_WIDTH" "$MCPE_RENDER_HEIGHT" >"$GAMEDIR/logs/crossmix-resolution-probe.log" 2>&1 || resolution_probe=$?
    if [ "$resolution_probe" != 0 ]; then
        unset CRUSTY_RESOLUTION
        export MCPE_RENDER_WIDTH="$WESTON_HEADLESS_WIDTH" MCPE_RENDER_HEIGHT="$WESTON_HEADLESS_HEIGHT"
        log "reduced_resolution_rejected probe_exit=$resolution_probe fallback=native"
    else
        log "reduced_resolution_surface_verified=${MCPE_RENDER_WIDTH}x${MCPE_RENDER_HEIGHT} full_panel_scaling=requires_physical_observation"
    fi
fi
# ARGS is the existing launcher protocol; split it without eval.
read -r -a extra_args <<<"${APP_EXTRA_ARGS:-}"
log "diagnostic_time_limit_seconds=${1:-0}"
cd "$GAMEDIR"
stage=client-start
timepoint client_exec
log "process=$client_role executable=$CLIENT game=$GAME log=$GAMEDIR/logs/crossmix-client.log"
log "data_root=$MCPELAUNCHER_DATA_DIR preloads=$MCPE_NATIVE_PRELOAD"
set +e
"$RUN" "$CLIENT" -dg "$GAME" -ww "$MCPE_RENDER_WIDTH" -wh "$MCPE_RENDER_HEIGHT" "${extra_args[@]}" \
    >"$GAMEDIR/logs/crossmix-client.log" 2>&1 &
client_pid=$!
log "process=$client_role pid=$client_pid"
(
    # This subshell owns its watchdog logic, not the parent's ERR/EXIT cleanup.
    trap - ERR EXIT INT TERM HUP
    seconds=0; shutdown=0
    while kill -0 "$client_pid" 2>/dev/null; do
        sleep 1
        seconds=$((seconds+1))
        if ! kill -0 "$weston_pid" 2>/dev/null; then
            timepoint weston_exited_before_client
            echo 'Weston exited; terminating this session client.' >>"$GAMEDIR/logs/crossmix-client.log"
            kill -TERM "$client_pid" 2>/dev/null || true
            sleep 3
            kill -KILL "$client_pid" 2>/dev/null || true
            break
        fi
        if grep -q 'Invoking stop activity callbacks' "$GAMEDIR/logs/crossmix-client.log"; then
            shutdown=$((shutdown+1))
        fi
        if [ "$shutdown" -ge 15 ] || { [ "${1:-0}" != 0 ] && [ "$seconds" -ge "${1:-0}" ]; }; then
            if [ "${1:-0}" != 0 ] && [ "$seconds" -ge "${1:-0}" ]; then
                echo "diagnostic_time_limit_reached=${1}s" >>"$GAMEDIR/logs/crossmix-client.log"
            else
                echo 'shutdown_grace_exceeded=15s' >>"$GAMEDIR/logs/crossmix-client.log"
            fi
            timepoint client_watchdog_term
            kill -TERM "$client_pid" 2>/dev/null || true
            sleep 3
            kill -KILL "$client_pid" 2>/dev/null || true
            timepoint client_watchdog_kill_attempt
            break
        fi
    done
) &
watcher_pid=$!
if [ -r "$GAMEDIR/crossmix/session_metrics.py" ]; then
    python3 "$GAMEDIR/crossmix/session_metrics.py" "$GAMEDIR" "$client_pid" "$weston_pid" >>"$SESSION_LOG" 2>&1 &
    metrics_pid=$!
fi
stage=client-wait
# An ERR trap still runs under set +e. Capture the child's exact status directly.
status=0
wait "$client_pid" || status=$?
log "process=$client_role exit_code=$status"
timepoint client_exit
weston_alive=0; kill -0 "$weston_pid" 2>/dev/null && weston_alive=1
xwayland_alive=unknown
if [ -r "$SESSION/xwayland.pid" ]; then
    read -r xwayland_pid <"$SESSION/xwayland.pid"
    case "$xwayland_pid" in ''|*[!0-9]*) ;; *)
        xwayland_alive=0; kill -0 "$xwayland_pid" 2>/dev/null && xwayland_alive=1 ;;
    esac
fi
log "process_state_at_client_end weston_alive=$weston_alive xwayland_alive=$xwayland_alive"
client_pid=
stage=client-finished
exit "$status"
