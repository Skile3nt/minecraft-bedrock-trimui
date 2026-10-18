#!/usr/bin/env python3
"""Build a small, verified 0.2.2 overlay over the preserved CrossMix port."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CROSSMIX = ROOT / 'crossmix'
DIST = ROOT / 'dist'
BASE = DIST / 'Minecraft-Bedrock-TrimUI-0.2.1-Performance-Overlay.zip'
BASE_SHA256 = 'df59fb41a0ff31f6cfb2539ba0e94f7f1dc9c21e6908ee6e03e78783dbd1602e'
VERSION = (CROSSMIX / 'ADAPTATION_VERSION').read_text().strip()
OUTPUT = DIST / f'Minecraft-Bedrock-TrimUI-{VERSION.removesuffix("-experimental")}-Performance-Overlay-r2.zip'
PREFIX = 'Data/ports/minecraftbedrock/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    assert VERSION == '0.2.2-experimental'
    base_bytes = BASE.read_bytes()
    assert sha(base_bytes) == BASE_SHA256, 'Preserved 0.2.1 overlay hash mismatch'
    with zipfile.ZipFile(BASE) as old:
        assert old.testzip() is None
        old_files = set(old.namelist())

    changes = {
        PREFIX + 'crossmix/ADAPTATION_VERSION': (CROSSMIX / 'ADAPTATION_VERSION').read_bytes(),
        PREFIX + 'crossmix/session.sh': (CROSSMIX / 'session.sh').read_bytes(),
        PREFIX + 'crossmix/performance_profiles.py': (CROSSMIX / 'performance_profiles.py').read_bytes(),
        PREFIX + 'crossmix/upstream-entry.sh': (ROOT / 'portmaster/minecraftbedrock/Minecraft Bedrock.sh').read_bytes(),
        PREFIX + 'menu/main.lua': (ROOT / 'portmaster/minecraftbedrock/minecraftbedrock/menu/main.lua').read_bytes(),
        PREFIX + 'crossmix/HOTFIX_0.2.2.md': (CROSSMIX / 'HOTFIX_0.2.2.md').read_bytes(),
    }
    assert PREFIX + 'crossmix/session.sh' in old_files
    assert PREFIX + 'crossmix/sdl-trace.so' in old_files
    with tempfile.TemporaryDirectory(prefix='mcpe-022-overlay-') as temp:
        trace = Path(temp) / 'sdl-trace.so'
        subprocess.run(['aarch64-linux-gnu-gcc', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-fPIC', '-shared', str(CROSSMIX / 'sdl-trace.c'), '-ldl', '-o', str(trace)], check=True)
        elf = subprocess.check_output(['aarch64-linux-gnu-readelf', '-h', str(trace)], text=True)
        assert 'AArch64' in elf and 'DYN (Shared object file)' in elf
        changes[PREFIX + 'crossmix/sdl-trace.so'] = trace.read_bytes()

    hashes = {name: sha(data) for name, data in sorted(changes.items())}
    manifest = {
        'version': VERSION,
        'based_on_overlay': BASE.name,
        'based_on_sha256': BASE_SHA256,
        'hardware_tested': False,
        'revision': 2,
        'purpose': 'Performance-only reversible FPS-cap A/B, bounded presentation trace, launcher setting; preserves native-resolution fallback.',
        'files': hashes,
    }
    changes[PREFIX + 'crossmix/PERFORMANCE_0.2.2_MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    DIST.mkdir(exist_ok=True)
    assert not OUTPUT.exists() and not Path(OUTPUT.with_suffix(OUTPUT.suffix + '.sha256')).exists(), 'Refusing to overwrite an existing package'
    with zipfile.ZipFile(OUTPUT, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(changes.items()):
            executable = name.endswith(('.sh', '.so'))
            info = zipfile.ZipInfo(name, (2026, 10, 15, 0, 0, 0))
            info.external_attr = (0o100755 if executable else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
        for name, digest in hashes.items():
            assert sha(archive.read(name)) == digest, name
        assert not any(name.lower().endswith(('.apk', '.apks', '.mcworld')) or 'libminecraftpe.so' in name
                       for name in archive.namelist())
    digest = sha(OUTPUT.read_bytes())
    OUTPUT.with_suffix(OUTPUT.suffix + '.sha256').write_text(f'{digest}  {OUTPUT.name}\n')
    print(f'{OUTPUT}\nsha256={digest}\nfiles={len(changes)}')


if __name__ == '__main__':
    main()
