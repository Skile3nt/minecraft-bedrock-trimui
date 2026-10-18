# Minecraft Bedrock 1.16 — TrimUI Smart Pro (CrossMix-OS)

**Community adaptation by Skile** · ARM64 · PowerVR GE8300 · CrossMix-OS · turquoise launcher (`#00FFEF`)

> **Source package — not a ready-to-install game or complete SD-card release.**  
> The Minecraft APK, game assets, saved worlds, account data, firmware runtime, precompiled launchers and third-party binary libraries are **not included**. A user must provide their own legally acquired Minecraft Bedrock **Android** copy and an appropriate compatible runtime. Do not extract this source archive directly to the TrimUI card expecting a playable game.

This project adapts the open-source [Minecraft Bedrock handheld port by DankMiimer](https://github.com/DankMiimer/minecraft-bedrock-handheld-port) and the [minecraft-linux](https://github.com/minecraft-linux) launcher ecosystem for the original **TrimUI Smart Pro**, running **CrossMix-OS**.

## TrimUI adaptation

- Tested with **Minecraft Bedrock Android 1.16.221.01** on the original TrimUI Smart Pro.
- CrossMix session/bootstrap work, SDL/EGL routing for PowerVR, gamepad bridge and on-device launcher configuration.
- Dark, retro-inspired menu with **turquoise `#00FFEF`** highlights; `Credits` includes **Port & Adaptation: Skile**.
- The only launcher menu options removed in this branch are `Help`, `Support Bundle` and `Update Port`.
- The launcher retains its other options and three game profiles.

**Hardware status:** gameplay/world creation previously confirmed by the device owner; L2/R2 remain a known issue. The latest turquoise revision passed automated tests but has **not yet passed a full physical before/after acceptance test**. Faster game loading/shutdown is not proven. See [`LAUNCHER_POLISH.md`](LAUNCHER_POLISH.md) and [`PUBLIC_RELEASE.md`](PUBLIC_RELEASE.md).

## Source layout

- [`crossmix/`](crossmix/) — TrimUI/CrossMix scripts, configuration, testing and build tooling.
- [`portmaster/`](portmaster/) — source scripts and original launcher structure; **precompiled binaries and uncertain-origin visual assets are omitted from this source archive**.
- [`source_release/`](source_release/) — patches and source for open-source runtime adaptations.
- [`tests/`](tests/) — automated tests.
- [`UPSTREAM_README.md`](UPSTREAM_README.md) — documentation of the underlying multi-device port (which covers other devices and releases; it should not be interpreted as TrimUI test evidence).

A release that other people can install requires a **separately validated runtime package** and an appropriate installer. [`PUBLIC_RELEASE.md`](PUBLIC_RELEASE.md) describes an **update over an already installed CrossMix adaptation**, not a fresh-install ZIP. Do not publish it as standalone until its original prerequisites and all included third-party components have been verified.

## Credits and licensing

**Skile:** TrimUI Smart Pro / CrossMix-OS port and customization.  
**DankMiimer:** original handheld-port framework, packaging and upstream work.  
**minecraft-linux**, **MCMrARM** and others: launcher and gamepad components; see [`CREDITS.md`](CREDITS.md), [`AUTHORS.md`](AUTHORS.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), [`LICENSE`](LICENSE) and [`LEGAL.md`](LEGAL.md).

GPL-3.0 licensed source and components retain their original notices. Other dependencies follow their own licenses. This project is **unofficial** and is **not approved by or affiliated with Mojang Studios or Microsoft**. Minecraft is proprietary and is **not included**.

## Optional skin

[`extras/Skile.mcpack`](extras/Skile.mcpack) is an optional, separate user-supplied skin pack. It does not replace Steve or bypass Microsoft/Xbox login. Recognition in this particular TrimUI launcher has **not** been verified on hardware.
