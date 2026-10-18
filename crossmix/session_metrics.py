#!/usr/bin/env python3
"""Bounded proc telemetry and named milestones; no text/input/auth recording."""
import json
import os
from pathlib import Path
import sys
import time

MARKERS = {'minecraft_library_loading': 'Loading Minecraft library',
           'minecraft_library_loaded': 'Loaded Minecraft library',
           'jni_onload': 'Entering JNI_OnLoad',
           'android_activity': 'Invoking ANativeActivity_onCreate',
           'minecraft_init': 'MinecraftGame::init',
           'xbox_sdk_registered': 'Successfully registerered XboxLiveAppConfig methods',
           'activity_stop_requested': 'Invoking stop activity callbacks',
           'x_connection_lost': 'X connection to'}


def now():
    return time.clock_gettime(getattr(time, 'CLOCK_BOOTTIME', time.CLOCK_MONOTONIC))


def emit(path, **values):
    with path.open('a') as f:
        f.write(json.dumps(dict(uptime=round(now(), 3), **values), separators=(',', ':'))+'\n')


def read_metrics(pid):
    root = Path('/proc')/str(pid)
    result = {'pid': pid}
    try:
        fields = root.joinpath('stat').read_text().rsplit(')', 1)[1].split()
        result['cpu_ticks'] = int(fields[11])+int(fields[12])
        for line in root.joinpath('status').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in ('VmRSS', 'VmHWM', 'VmSize', 'Threads'):
                result[key] = int(value.split()[0])
    except (OSError, ValueError, IndexError):
        result['exited_or_unreadable'] = True
        return result
    try:
        for line in root.joinpath('io').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in ('rchar', 'read_bytes', 'write_bytes'): result[key] = int(value)
        result['io_available'] = True
    except (OSError, ValueError): result['io_available'] = False
    return result


def read_thread_cpu(pid, previous=None, window_seconds=0, proc_root=Path('/proc'), hz=None):
    """Sparse top-thread CPU attribution; percentages are relative to one core."""
    hz = hz or os.sysconf('SC_CLK_TCK')
    tasks = Path(proc_root)/str(pid)/'task'
    current = {}
    ranked = []
    try: entries = list(tasks.iterdir())
    except OSError: return {}, []
    for entry in entries:
        try:
            tid = int(entry.name)
            fields = entry.joinpath('stat').read_text(errors='replace').rsplit(')', 1)[1].split()
            ticks = int(fields[11])+int(fields[12])
            name = entry.joinpath('comm').read_text().strip()[:15]
        except (OSError, ValueError, IndexError):
            continue
        current[tid] = (name, ticks)
        old = (previous or {}).get(tid)
        if old and old[0] == name and window_seconds > 0:
            delta = max(0, ticks-old[1])
            ranked.append({'tid':tid, 'name':name,
                           'cpu_percent_one_core':round(100*delta/hz/window_seconds, 1)})
    ranked.sort(key=lambda row: row['cpu_percent_one_core'], reverse=True)
    return current, ranked[:5]


def system_metrics():
    cores = {}
    for line in Path('/proc/stat').read_text().splitlines():
        parts=line.split()
        if parts and parts[0].startswith('cpu') and parts[0][3:].isdigit():
            cores[parts[0]]=[int(x) for x in parts[1:9]]
    clocks={}
    for path in Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/scaling_cur_freq'):
        try:clocks[path.parent.parent.name]=int(path.read_text())
        except (OSError,ValueError): pass
    thermal={}
    for path in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
        try:thermal[path.parent.name]=int(path.read_text())
        except (OSError,ValueError): pass
    disk={}
    for line in Path('/proc/diskstats').read_text().splitlines():
        p=line.split()
        if len(p)>=14 and p[2] in ('mmcblk1','mmcblk1p1'):
            disk[p[2]]={'read_sectors':int(p[5]),'read_ms':int(p[6]),'io_ms':int(p[12])}
    pressure=Path('/proc/pressure/memory')
    try:psi=pressure.read_text().strip() if pressure.exists() else None
    except OSError:psi=None
    cooling={}
    for path in Path('/sys/class/thermal').glob('cooling_device*/cur_state'):
        try:cooling[path.parent.name]=int(path.read_text())
        except (OSError,ValueError):pass
    return {'cpu_core_ticks':cores,'cpu_khz':clocks,'thermal_millidegrees':thermal,'cooling_states':cooling,
            'sd_global_io':disk,'memory_pressure':psi}


def main():
    game = Path(sys.argv[1]); client = int(sys.argv[2]); weston = int(sys.argv[3])
    path = game/'logs/crossmix-performance.jsonl'
    client_log = game/'logs/crossmix-client.log'; offset = 0; tail = ''; seen = set()
    emit(path, event='metrics_start', clock_ticks=os.sysconf('SC_CLK_TCK'),
         interval_seconds=2, marker_precision='first observation, up to 2s polling delay')
    xwayland_seen = False
    thread_previous = {}; thread_previous_uptime = None
    for sample in range(900):  # max 30 minutes, <= a few hundred KiB
        try: os.kill(client, 0)
        except ProcessLookupError: break
        with client_log.open(errors='replace') as f:
            f.seek(offset); text = tail+f.read(); offset = f.tell(); tail = text[-200:]
        for name, marker in MARKERS.items():
            if name not in seen and marker in text:
                emit(path, event=name, observed=True); seen.add(name)
        memory = {}
        for line in Path('/proc/meminfo').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in ('MemAvailable', 'MemFree', 'SwapFree', 'SwapTotal', 'Dirty','Cached','Buffers','SReclaimable'): memory[key] = int(value.split()[0])
        oom = next((int(s.split()[1]) for s in Path('/proc/vmstat').read_text().splitlines()
                    if s.startswith('oom_kill ')), None)
        xwayland = {}
        try:
            pid = int(Path(os.environ['MCPE_SESSION_DIR'], 'xwayland.pid').read_text())
            xwayland = read_metrics(pid)
            if not xwayland_seen and not xwayland.get('exited_or_unreadable'):
                emit(path, event='xwayland_process_observed', observed=True); xwayland_seen = True
        except (OSError, ValueError, KeyError): pass
        thread_values = {}
        if sample % 5 == 0:  # task scan every 10s, keeping telemetry overhead bounded
            observed = now()
            snapshot, top = read_thread_cpu(
                client, thread_previous,
                observed-thread_previous_uptime if thread_previous_uptime is not None else 0)
            if thread_previous_uptime is not None:
                thread_values = {'thread_cpu_window_seconds':round(observed-thread_previous_uptime, 1),
                                 'top_threads_by_cpu_one_core':top}
            thread_previous, thread_previous_uptime = snapshot, observed
        emit(path, event='sample', sample=sample, client=read_metrics(client),
             weston=read_metrics(weston), xwayland=xwayland, memory_kib=memory, system_oom_kill=oom,
             system=system_metrics(), **thread_values)
        time.sleep(2)


if __name__ == '__main__': main()
