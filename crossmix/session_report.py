#!/usr/bin/env python3
"""Report the first error before teardown; log markers do not prove gameplay."""
import datetime
import json
import os
from pathlib import Path
import re
import sys


def summarize(logs, status, stage):
    def read(name):
        p = logs/name
        return p.read_text(errors='replace') if p.exists() else ''
    client = read('crossmix-client.log'); weston = read('crossmix-weston.log')
    client = client.split('CrossMix cleanup_begin', 1)[0]
    weston = weston.split('CrossMix cleanup_begin', 1)[0]
    session = read('crossmix-session.log')
    # Cleanup is now measured before reporting. Its errors cannot become the
    # original startup/shutdown cause, even if Weston reports a teardown fault.
    session_before_cleanup = session.split('cleanup=stopping owned client/Weston', 1)[0]
    # Strip terminal control codes without changing the archived original log.
    client = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', client)
    client_role = 'sdl-session-probe' if 'process=sdl-session-probe pid=' in session else 'mcpelauncher-client'
    spawned = f'process={client_role} pid=' in session
    graphics_failure = re.search(r'CrossMix graphics_failure step=(\S+) SDL_GetError=(.*)', client)
    version = re.search(r'CrossMix native_SDL_version=(\S+)', client)
    driver = re.search(r'graphics_end step=SDL_Init result=\S+ driver=(\S+)', client)
    state = re.search(r'process_state_at_client_end weston_alive=(\S+) xwayland_alive=(\S+)', session)
    def alive(value): return True if value == '1' else False if value == '0' else None
    bindings = [s for s in client.splitlines() if s.startswith('CrossMix binding ')]
    time_limit = 'diagnostic_time_limit_reached=' in client
    original = None; fatal = None; component = None
    # Optional FMOD warning is not fatal. This runs before our teardown, so its
    # TERM / Broken pipe / compositor cleanup assertion cannot become the cause.
    patterns = [(r'No current EGL context or display', 'crusty-egl', False),
                (r'CrossMix graphics_failure', 'sdl-egl', True),
                (r'SDL_EGL_CreateSurface fail|Could not create SDL Window|Could not init SDL', 'sdl-egl', True),
                (r'EGLUT: failed', 'eglut', True),
                (r'error while loading shared libraries|symbol lookup error', 'dynamic-loader', True),
                (r'Failed to load Minecraft library', 'android-game-loader', True)]
    for line in client.splitlines():
        for pattern, role, is_fatal in patterns:
            if re.search(pattern, line):
                if original is None: original = line
                if is_fatal and fatal is None: fatal, component = line, role
                break
    if status and component is None:
        component = 'client' if spawned else stage
        if component == 'weston-start':
            original = next((s for s in weston.splitlines() if 'failed' in s.lower()), None)
    message = {'sdl-egl': 'SDL/EGL window failed', 'eglut': 'EGLUT config failed',
               'dynamic-loader': 'ARM64 library loader failed',
               'android-game-loader': 'Minecraft library load failed',
               'weston-start': 'Weston session failed'}.get(component, f'{component or stage} failed')
    if graphics_failure: message = graphics_failure.group(1)+' failed'
    if time_limit and component == 'client': component, message = 'diagnostic-time-limit', 'Diagnostic time limit reached'
    if status and fatal is None and 'shutdown_grace_exceeded=' in client:
        component, message = 'shutdown-timeout', 'Minecraft shutdown exceeded 15s grace'
    if status and fatal is None and 'Weston exited; terminating this session client.' in client:
        component, message = 'weston-runtime-exited', 'Weston exited while Minecraft was active'
    interruption = re.search(r'session_signal=(\S+) stage=(\S+)', session_before_cleanup)
    profile = re.search(r'performance_profile=(\S+) render_requested=(\S+)',session)
    if interruption and fatal is None:
        component, message = 'external-session-signal', 'Session interrupted by '+interruption.group(1)
    elif status and fatal is None and 'X connection to' in client and component == 'client':
        component, message = 'xwayland-connection-lost', 'Minecraft lost its Xwayland connection'
        original = next((s for s in client.splitlines() if 'X connection to' in s), original)
    performance = []
    for line in read('crossmix-performance.jsonl').splitlines():
        try: performance.append(json.loads(line))
        except ValueError: pass
    return {'exit_code': status, 'stage': stage, 'failed_component': component,
            'session_signal': interruption.group(1) if interruption else None,
            'shutdown_watchdog_triggered': 'shutdown_grace_exceeded=' in client,
            'state': 'finished',
            'performance_profile': profile.group(1) if profile else None,
            'render_requested': profile.group(2) if profile else None,
            'resolution_fell_back_to_native': 'reduced_resolution_rejected' in session,
            'resolution_surface_probe_passed': 'reduced_resolution_surface_verified=' in session,
            'failed_process': (client_role if spawned else
                               'weston' if stage == 'weston-start' else 'session') if status else None,
            'first_error': original, 'first_fatal': fatal, 'screen_message': message,
            'weston_listening': 'xserver listening on display' in weston,
            'xwayland_spawned': "launching '" in weston and 'xwayland' in weston,
            'xwayland_wm_ready': 'created wm, root' in weston,
            'client_spawned': spawned,
            'graphics_failed_step': graphics_failure.group(1) if graphics_failure else None,
            'bounded_diagnostic_timeout': time_limit,
            'sdl_error': graphics_failure.group(2) if graphics_failure else None,
            'sdl_version': version.group(1) if version else None,
            'sdl_video_driver': driver.group(1) if driver else None,
            'weston_alive_at_client_end': alive(state.group(1)) if state else None,
            'xwayland_alive_at_client_end': alive(state.group(2)) if state else None,
            'graphics_process_observations': [s for s in client.splitlines() if s.startswith('CrossMix graphics_process_state ')],
            'graphics_bindings': bindings,
            'native_symbol_origins': [s for s in client.splitlines() if s.startswith('CrossMix symbol=')],
            'loaded_objects': [s for s in client.splitlines() if s.startswith(('CrossMix audit_object=', 'CrossMix loaded_object='))],
            'egl_error_observations': [s for s in client.splitlines() if s.startswith(('CrossMix terminal_eglGetError=', 'CrossMix forwarded_eglGetError='))],
            'egl_error_note': 'terminal_eglGetError is after SDL failure and may already have been consumed; forwarded values are unchanged original calls',
            'android_linker_loaded': 'linker loaded' in client,
            'android_activity_started': 'Invoking ANativeActivity_onCreate' in client,
            'activity_stop_requested': 'Invoking stop activity callbacks' in client,
            'x_connection_lost': 'X connection to' in client,
            'input_diagnostics': read('crossmix-input.log').splitlines()[:220],
            'timing_events': [p for p in performance if p.get('event') != 'sample'],
            'memory_available_min_kib': min((p['memory_kib']['MemAvailable'] for p in performance
                                            if p.get('event') == 'sample'), default=None),
            'client_rss_max_kib': max((p.get('client', {}).get('VmRSS', 0) for p in performance
                                      if p.get('event') == 'sample'), default=None),
            'measurement_limits': 'First swap does not prove a visible image; Xbox SDK registration does not prove welcome UI. Proc samples every 2s; no comparable before/after benchmark.',
            'minecraft_library_loading_seen': 'Loading Minecraft library' in client,
            'minecraft_library_loaded_seen': 'Loaded Minecraft library' in client,
            # A world-level marker prevents an early quit after play began
            # from being mislabeled as a failed startup by the failsafe.
            'world_loaded_seen': 'Player connected:' in client,
            'minecraft_execution': 'unconfirmed; markers describe initialization only',
            'crusty_route_recovered': 'backend_route_recovered' in client}


def main():
    logs = Path(sys.argv[1])/'logs'; status = int(sys.argv[2]); stage = sys.argv[3]
    report = summarize(logs, status, stage)
    report['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data = json.dumps(report, indent=2)+'\n'
    (logs/'crossmix-session-report.json').write_text(data)
    if status: (logs/'crossmix-failure.txt').write_text(report['screen_message']+'\n')
    archive = logs/'attempts'/(report['timestamp'].replace(':', '-')+'-'+str(os.getpid()))
    archive.mkdir(parents=True)
    (archive/'report.json').write_text(data)
    for name in ('crossmix-client.log', 'crossmix-weston.log', 'crossmix-session.log', 'crossmix-runtime-inventory.json', 'crossmix-input.log', 'crossmix-performance.jsonl', 'crossmix-frames.jsonl', 'crossmix-profile-018.json', 'crossmix-resolution-probe.log', 'crossmix-particle-audit.log'):
        if (logs/name).exists(): (archive/name).write_bytes((logs/name).read_bytes())
    print('session_summary='+json.dumps(report, separators=(',', ':')))


if __name__ == '__main__': main()
