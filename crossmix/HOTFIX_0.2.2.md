# Performance Engineering 0.2.2

The Performance profile now has a reversible A/B cap selection: 30, 40, or 50
in the existing launcher Settings screen. The selected value is temporarily
written to the existing `gfx_max_framerate` option by the profile journal and
restored when the session exits. Original and No Particles do not use this cap.
The session log records the requested value and the option value before restore.
The game may clamp or ignore 40/50; this requires a physical comparison. When
the failsafe rung is active, the experiment is disabled and its 30/20 cap stays
in control.

The Crusty presentation trace retains batches of 240 swap intervals but stops
after 225 records (about 30 minutes at 30 submissions/s). It stays in session
tmpfs and is copied to the SD once at cleanup. The rate is presentation-call
cadence, not verified scanout FPS or unique game images. The global limit is
checked once per completed batch, then collection disables on that thread; no
atomic limit check is added to each presentation call.

The Performance profile still requests 1024×576 and retains the existing EGL
size gate. If the native EGL probe reports the panel's 1280×720 surface, the
session falls back to 1280×720. Do not override this fallback: the last device
log showed SDL requested 1024×576 while PowerVR's native `MALI_CreateWindow`
path returned an EGL surface of 1280×720. The device does not prove that the
driver itself forbids a smaller offscreen framebuffer; no second renderer was
added.

## Physical A/B

Use the same world, position, view distance, route, and Performance settings.
Warm up for 60 seconds, then collect 120 seconds at each cap (30, 40, 50),
repeating each run three times if practical. In the launcher choose **Game
profile → Performance**, then **Settings → Performance profile cap**. Keep
VSync and all other settings unchanged. Confirm each session log contains
`performance_fps_cap_requested=<value>` and
`performance_fps_cap_option_at_exit=<value>`; those confirm the option handoff,
not that the proprietary game honored its internal cap. For raw app frame/swap
timings, enable **Settings → FPS logging** for all runs; those are not panel
scanout measurements and their per-frame `getrusage` overhead may perturb the
result. The default batched trace is lower overhead.

Rollback: select a different profile/cap to restore automatically after the
session. To revert the code overlay, restore the backed-up files or extract the
preserved 0.2.1 overlay; do not restore user `options.txt` from a stale backup.

This overlay was validated on the PC and under ARM64 QEMU only. It has not been
installed or tested on the TrimUI. Audio, worlds, controls, assets, Crusty,
Weston, EGL, and the native fallback were not intentionally changed.
