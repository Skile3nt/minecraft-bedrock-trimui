# Performance Engineering 0.2.3 — cumulative experimental overlay

This package includes the post-0.1.9 launcher profile/cap selection, the paired
failsafe and world-marker report correction, thread telemetry, monotonic
presentation timing, bounded tmpfs batches, and the reversible 30/40/50 cap
experiment. Earlier 0.2.2 overlays assumed some of these files were already
installed. The 0.2.3 manifest names all replacement files and baseline hashes.

The three small ARM64 adapter libraries are rebuilt from the included sources.
The runtime, graphics driver, input bridge, controls and game assets stay as
installed. The resolution probe and native-size fallback remain authoritative.
No new hardware performance result is implied by packaging or host tests.

Do not extract this overlay onto an unverified FAT filesystem. First confirm
the CROSSMIXOS UUID/serial and complete an unmounted, read-only filesystem
check. Back up every differing listed file before the first replacement;
record formerly absent paths and verify both backup and installed hashes.
An existing newer customization must be examined before replacing it.

Live settings are deliberately absent from the ZIP. Preserve the current
`config/performance-018.json` and the selected profile. If updating a pristine
0.1.9 installation, its null/missing `texture_dequeue` requires a separately
backed-up key-only migration to 4 to reproduce the already-established
Performance profile. Do not replace the whole config with the shipped default
template. Existing explicit values, especially 4, must be preserved.

Rollback restores the backed-up code and removes only newly installed files
whose current hashes still match this package. Preserve later edits and user
data; never roll back worlds, accounts, options or resource packs from stale
copies. Keep all earlier ZIPs and the installation/backup manifest.

Physical validation: launch Play using the same profile/world, verify L2/R2,
audio, No Particles and classic textures, then warm up 60 seconds and repeat
the same 120-second route. Compare presentation median/P95/P99 at the same
cap first. Test 30/40/50 separately; presentations are not confirmed unique
frames or panel FPS. Shutdown mutex failure remains a separate known issue.
