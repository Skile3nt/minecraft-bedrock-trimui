#!/bin/sh
# CrossMix starts Ports with /bin/sh, independently of the shebang.
# This line is specialized by build.py for each self-contained menu entry.
entry_mode=${1:-}
stage=bootstrap
entry_path=$0
case "$entry_path" in /*) ;; *) entry_path="$PWD/$entry_path" ;; esac
entry_dir=$(CDPATH= cd -- "${entry_path%/*}" 2>/dev/null && pwd)
card_root=$(CDPATH= cd -- "$entry_dir/../.." 2>/dev/null && pwd)
GAMEDIR="$card_root/Data/ports/minecraftbedrock"
bootstrap_log=/tmp/minecraft-bedrock-bootstrap.log
if [ -n "$entry_dir" ] && [ -d "$GAMEDIR" ] && mkdir -p "$GAMEDIR/logs"; then
    if ( : >>"$GAMEDIR/logs/crossmix-entry.log" ) 2>/dev/null; then
        bootstrap_log="$GAMEDIR/logs/crossmix-entry.log"
    fi
fi
if [ "$bootstrap_log" = /tmp/minecraft-bedrock-bootstrap.log ] && [ -d "$entry_dir" ]; then
    if ( : >>"$entry_dir/Minecraft Bedrock bootstrap.log" ) 2>/dev/null; then
        bootstrap_log="$entry_dir/Minecraft Bedrock bootstrap.log"
    fi
fi
# Record failures before Python, Bash, SDL or the GPU are touched.
exec >>"$bootstrap_log" 2>&1
printf '\n=== CrossMix bootstrap %s pid=%s ===\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$$"
printf 'entry=%s\nmode=%s\ncwd=%s\nentry_dir=%s\ncard_root=%s\nlog=%s\n' "$0" "$entry_mode" "$PWD" "$entry_dir" "$card_root" "$bootstrap_log"
finish() {
    result=$?
    trap - 0
    printf 'stage=%s exit_code=%s\n' "$stage" "$result"
    if [ -r "$GAMEDIR/crossmix/status.sh" ] && { [ "$entry_mode" = --diagnose ] || [ "$entry_mode" = --sdl-test ] || [ "$entry_mode" = --input-test ] || [ "$result" -ne 0 ]; }; then
        if [ "$entry_mode" = --sdl-test ]; then
            message="SDL Test finished (code $result). See logs/crossmix-sdl-test.json"
        elif [ "$entry_mode" = --input-test ] && [ "$result" -eq 0 ]; then
            message='Input Test saved. See logs/crossmix-input-test.json'
        elif [ "$result" -eq 0 ]; then
            message='Minecraft Diagnostics: checks OK. Logs saved.'
        else
            message="Minecraft: failed at $stage (code $result). See crossmix-entry.log"
            if [ "$stage" = launcher ] && [ -r "$GAMEDIR/logs/crossmix-failure.txt" ]; then
                detail=
                IFS= read -r detail <"$GAMEDIR/logs/crossmix-failure.txt" || :
                [ -z "$detail" ] || message="Minecraft: $detail (code $result). See crossmix-session-report.json"
            fi
        fi
        sh "$GAMEDIR/crossmix/status.sh" "$message" || :
    fi
    if [ "$stage" = launcher ] && [ -f "$GAMEDIR/logs/crossmix-performance.jsonl" ]; then
        read -r return_uptime rest </proc/uptime || return_uptime=
        case "$return_uptime" in ''|*[!0-9.]*) ;; *)
            printf '{"uptime":%s,"event":"entry_return"}\n' "$return_uptime" >>"$GAMEDIR/logs/crossmix-performance.jsonl" ;;
        esac
    fi
    printf '=== bootstrap finished exit_code=%s ===\n' "$result"
    exit "$result"
}
trap finish 0
trap 'exit 130' INT
trap 'exit 143' TERM
set -eu
if [ -r /proc/uptime ]; then
    read -r MCPE_BOOT_UPTIME rest </proc/uptime
    export MCPE_BOOT_UPTIME
fi
export GAMEDIR
export MCPE_CARD_ROOT="$card_root"
[ -d "$GAMEDIR/crossmix" ] || { echo 'Port directory missing; extract Roms and Data at SD root.'; exit 1; }
export MCPE_CROSSMIX=1 MCPE_CFW_OVERRIDE=crossmix CFW_NAME=TrimUI
export MCPE_SHARED_ROOT="$GAMEDIR"
export MCPE_GAMEDIR_OVERRIDE="$GAMEDIR" MCPE_ENTRY_DIR_OVERRIDE="$entry_dir"
export MCPE_PM_INITIALIZED=1 DEVICE_ARCH=aarch64 ESUDO= GPTOKEYB= GPTOKEYB2=
export PM_CONTROL_ROOT="$card_root/Apps/PortMaster/PortMaster"
export controlfolder="$PM_CONTROL_ROOT"
export PATH="$GAMEDIR/crossmix/bin:$card_root/System/bin:$PATH"
# Firmware libraries serve Python, LOVE and the native status viewer.
export LD_LIBRARY_PATH="$card_root/System/lib:/usr/trimui/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export SDL_GAMECONTROLLERCONFIG_FILE="$PM_CONTROL_ROOT/gamecontrollerdb.txt"
export SDL_VIDEODRIVER=mali SDL_DRIVER_OVERRIDE=mali
export MCPE_GRAPHICS_BACKEND=mali MCPE_ABI_OVERRIDE=arm64
export MCPE_LOVE_TXT_OVERRIDE="$GAMEDIR/crossmix/love.txt"
export MCPE_MENU=1 MCPE_MENU_EXIT_ON_PLAY=1 MCPE_MANAGE_FRONTEND=0
export MCPE_MAX_FPS_LEGACY=30 MCPE_MAX_FPS_MODERN=30
export MCPE_PERFORMANCE_MODE=0 MCPE_PREWARM_GAMEPLAY_ASSETS=0
export MCPE_SCREENSHOTS=0
stage=paths
mkdir -p "$GAMEDIR/config" "$GAMEDIR/apk" "$GAMEDIR/versions" "$GAMEDIR/profiles" "$GAMEDIR/backups"
printf 'architecture=%s\nPATH=%s\nLD_LIBRARY_PATH=%s\n' "$(uname -m)" "$PATH" "$LD_LIBRARY_PATH"
ls -ld "$entry_dir" "$GAMEDIR" "$GAMEDIR/crossmix/bin" "$card_root/System/bin/python3.11" "$card_root/System/lib/python3.11/encodings" || :
stage=architecture
case "$(uname -m)" in aarch64|arm64) ;; *) echo 'TrimUI ARM64 is required.'; exit 1;; esac
stage=python
if python3 -c 'import ctypes, hashlib, json, sys, zipfile; print("python_version="+sys.version); print("python_prefix="+sys.prefix)'; then
    echo 'python_status=0'
else
    result=$?; echo "python_status=$result"; exit "$result"
fi
stage=probe
if python3 "$GAMEDIR/crossmix/probe.py" --output "$GAMEDIR/logs/crossmix-probe.json"; then
    probe_result=0
else
    probe_result=$?
fi
printf 'probe_status=%s\n' "$probe_result"
# Diagnostics must still check Bash when graphics discovery reports a problem.
stage=private-bash
if sh "$GAMEDIR/crossmix/bin/bash" -c 'printf "bash_version=%s\n" "$BASH_VERSION"; a=(ok); [[ ${a[0]} == ok ]]'; then
    echo 'bash_status=0'
else
    result=$?; echo "bash_status=$result"; exit "$result"
fi
if [ "$entry_mode" = --finalize ]; then
    # One-time, reversible cleanup for the final single-entry PortMaster UI.
    # It only moves the known legacy entries belonging to this port; the
    # migration never scans or changes other games in Roms/PORTS.
    stage=menu-cleanup
    python3 "$GAMEDIR/crossmix/cleanup_menu.py" "$entry_dir" "$GAMEDIR"
    entry_mode=
fi
case "$entry_mode" in
  --original|--no-particles|--no-particles-assets|--performance)
    case "$entry_mode" in
      --original) MCPE_PERF_PROFILE=ORIGINAL ;;
      --no-particles) MCPE_PERF_PROFILE=NO_PARTICLES; export MCPE_PARTICLE_METHOD=assets ;;
      --no-particles-assets) MCPE_PERF_PROFILE=NO_PARTICLES; export MCPE_PARTICLE_METHOD=assets ;;
      --performance) MCPE_PERF_PROFILE=PERFORMANCE; export MCPE_PARTICLE_METHOD=assets ;;
    esac
    export MCPE_PERF_PROFILE
    [ "$probe_result" -eq 0 ] || { stage=probe; exit "$probe_result"; }
    stage=launcher
    : >"$GAMEDIR/logs/crossmix-failure.txt"
    sh "$GAMEDIR/crossmix/bin/bash" "$GAMEDIR/crossmix/upstream-entry.sh"
    ;;
  --diagnose) stage=diagnostics-complete; exit "$probe_result" ;;
  --graphics-test) stage=graphics-test; sh "$GAMEDIR/crossmix/gpu-test.sh" ;;
  --sdl-test) stage=sdl-session-test; sh "$GAMEDIR/crossmix/bin/bash" "$GAMEDIR/crossmix/sdl-test.sh" ;;
  --input-test) stage=input-test; python3 "$GAMEDIR/crossmix/input-test.py" ;;
  '')
    [ "$probe_result" -eq 0 ] || { stage=probe; exit "$probe_result"; }
    stage=launcher
    # Invalidate previous failure text even when this launch fails before session.
    : >"$GAMEDIR/logs/crossmix-failure.txt"
    sh "$GAMEDIR/crossmix/bin/bash" "$GAMEDIR/crossmix/upstream-entry.sh"
    ;;
  *) stage=arguments; echo 'Unsupported entry argument.'; exit 2 ;;
esac
