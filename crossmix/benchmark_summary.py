#!/usr/bin/env python3
"""Summarize explicit time windows; submission intervals are not scanout FPS."""
import argparse
import json
from pathlib import Path


def rows(path):
    result=[]
    if path.exists():
        for line in path.read_text().splitlines():
            try:result.append(json.loads(line))
            except ValueError:pass
    return result


def summarize(logs, after=60, duration=120):
    records=rows(logs/'crossmix-performance.jsonl')
    hz=next((r['clock_ticks'] for r in records if r.get('event')=='metrics_start'),100)
    start=next((r['uptime'] for r in records if r.get('event')=='client_exec'),0)+after
    samples=[r for r in records if r.get('event')=='sample' and start<=r['uptime']<=start+duration]
    frames=[r for r in rows(logs/'crossmix-frames.jsonl') if start<=r['uptime']-r['seconds'] and r['uptime']<=start+duration]
    result={'window_after_client_seconds':after,'window_duration_requested':duration,'proc_samples':len(samples),
            'frame_metric':'verified Crusty -> native SDL present-return intervals; not physical scanout or guaranteed world-only FPS',
            'batches':len(frames),'physical_gpu_validation':False}
    if frames:
        seconds=sum(r['seconds'] for r in frames);n=sum(r['intervals'] for r in frames)
        result.update(submission_rate=n/seconds, per_batch_statistics=[
            {k:r[k] for k in ['uptime','median_ms','p95_ms','p99_ms','max_ms','egl_surface','viewport','fbo']} for r in frames])
        # Percentiles cannot be pooled from individual batch percentiles.
    if samples:
        result.update(memory_available_min_kib=min(r['memory_kib']['MemAvailable'] for r in samples),
            rss_peak_kib=max(r['client'].get('VmHWM',0) for r in samples))
    if len(samples)>1:
        a,b=samples[0],samples[-1];elapsed=b['uptime']-a['uptime']
        result['process_average_cpu_cores']=(b['client'].get('cpu_ticks',0)-a['client'].get('cpu_ticks',0))/hz/elapsed
        cores={}
        for core,last in b.get('system',{}).get('cpu_core_ticks',{}).items():
            first=a.get('system',{}).get('cpu_core_ticks',{}).get(core)
            if first:
                delta=[x-y for x,y in zip(last,first)];total=sum(delta)
                if total>0:cores[core]=100*(total-delta[3]-delta[4])/total
        result['cpu_per_core_busy_percent']=cores
    result['driver_reported_cpu_khz']=[r.get('system',{}).get('cpu_khz',{}) for r in samples]
    result['thermal_millidegrees']=[r.get('system',{}).get('thermal_millidegrees',{}) for r in samples]
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('logs',type=Path);p.add_argument('--after-seconds',type=float,default=60)
    p.add_argument('--duration',type=float,default=120);args=p.parse_args()
    print(json.dumps(summarize(args.logs,args.after_seconds,args.duration),indent=2))


if __name__=='__main__':main()
