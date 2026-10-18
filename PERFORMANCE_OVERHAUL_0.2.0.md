# Performance Overhaul 0.2.0 — Pass A

## Hardware evidence

The real CrossMix card was confirmed read/write as `CROSSMIXOS`; its port is
0.1.9-experimental. Logs are from TrimUI runs on 2026-10-14. The newest run
(22:35 UTC) selected **No Particles**, not Performance, and exited 137 without
a recorded fatal error; the kernel OOM counter was unavailable. Do not use it
as a Performance A/B result.

That run produced 26 bounded batches of 240 Crusty-to-native-SDL present-call
intervals. Every EGL surface was 1280×720; the viewport read 1281×720. In the
21 batches after the first five, median batch interval medians were 34.06 ms,
median batch P95 38.28 ms, median batch P99 43.83 ms, and median submission
rate 29.0 calls/s. These are **present-call cadence**, not gameplay FPS or
panel scanout. A startup batch had a 7.63 s interval; later batches reached
1.83 s. These stalls are not attributable to chunks or I/O from the data.

During the 60–180 s window, the client averaged 1.03 CPU cores; aggregate
per-core busy was 18–40%. The sampler cannot name the hot client thread yet.
All reported CPU frequencies remained 2.0 GHz; CPU thermal zone peaked at
67.6 °C in the whole session, with no cooling-state transition recorded. This
does not establish absence of throttling. Client RSS peaked at 477 MiB and
MemAvailable fell to 323 MiB, with no swap configured. This argues against
adding large caches, but does not prove memory pressure caused the stalls.
The OOM counter was unavailable. SD counters are system-wide; client I/O was
unavailable. No reliable world-ready marker or GPU utilization/frequency
counter was available (`pvrsrvkm` exposes no devfreq node in this sysfs view).

## Change in Pass A

Keep existing profiles and graphics behavior. The existing resolution gate,
4-texture Performance budget, bounded frame batches, and 2-second system
sampler remain unchanged. The existing collector now records the five busiest
client threads every 10 seconds, as one-core CPU percentages over that window.
This is diagnostic instrumentation only; it is not a performance improvement.

## Physical A/B still required

The installed logs do not contain a Performance run: all recorded runs used
Original or No Particles at 1280×720. Next, launch **Original** and then
**Performance** from Ports. Use the same existing world, fixed route through
already generated terrain, 5-chunk distance, classic pack, and equal 60-second
warm-up plus 120-second capture. Allow similar cool-down between runs. Save
`logs/crossmix-session-report.json`, `crossmix-performance.jsonl`, and
`crossmix-frames.jsonl` after each run. Confirm Performance reports the EGL
surface and game viewport at 1024×576 before attributing any change to fewer
pixels; confirm panel fill and menu readability on the device. Repeat each
profile three times. Treat submission calls as a proxy, never as FPS.

Do not change governors, frequencies, VSync, affinity, chunk distance, or
resource caching until that controlled comparison identifies a bottleneck.
The 4-versus-8 texture budget also needs its own same-profile physical A/B.

## Rollback

Restore the exact previous `crossmix/session_metrics.py` from the SD backup
created with this pass, or revert its Git commit. No game options, saves,
worlds, resource packs, controls, or system settings are changed by this pass.
