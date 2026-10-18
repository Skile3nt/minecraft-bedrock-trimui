# 0.2.1 Performance hotfix

The existing Crusty frame-batch observer performed `fopen`/append/`fclose` on
the render thread every 240 presentations. The session now writes batches to
its private `/tmp` directory and copies the result to the persistent log after
the client exits. Its data and meaning are unchanged: intervals between
verified Crusty presentation calls, not physical scanout or gameplay FPS.
Intervals use `CLOCK_MONOTONIC`; a detected suspend/resume resets a partial
batch, while separate boot uptime remains available for log correlation. Awake
stalls remain measurable.

The installed physical log also shows that 1024×576 was rejected: the requested
SDL size was 1024×576 while native EGL reported 1280×720. The existing fallback
to native size is retained. No evidence supports changing the graphics driver,
VSync, FPS cap, CPU affinity, or texture budget in this update.

Rollback the code change by restoring the previous `crossmix/session.sh`; the
existing `crossmix-frames.jsonl` format and game data are unaffected. Physical
performance improvement remains to be measured on the TrimUI.
