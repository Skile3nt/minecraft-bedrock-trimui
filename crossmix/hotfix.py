#!/usr/bin/env python3
"""Repack the immutable 0.1.1 ZIP with the device-log probe fix; no ARM execution."""
import hashlib, json, zipfile
from pathlib import Path
C = Path(__file__).resolve().parent
BASE_SHA = 'cd853a54e2f9db58805ebe02e78b3cf1d21118f83b2b8c4a33049689d05a827e'
BASE = (Path.home() / 'Downloads' / 'Minecraft-Bedrock-TrimUI-0.1.1-experimental.zip')
OUTPUT = C.parent/'dist/minecraft-bedrock-crossmix-0.1.1-experimental-probe-fix.zip'
PREFIX = 'Data/ports/minecraftbedrock/crossmix/'


def digest(data): return hashlib.sha256(data).hexdigest()


def main():
    assert digest(BASE.read_bytes()) == BASE_SHA, 'Base ZIP differs; refusing to modify'
    replacements = {PREFIX+name: (C/name).read_bytes() for name in
                    ('probe.py', 'probe_policy_test.py', 'hotfix.py', 'README.md', 'AUDIT.md')}
    replacements['Minecraft-Bedrock-CrossMix-README.md'] = (C/'README.md').read_bytes()
    metadata = {'id': 'probe-node-warning-1', 'base_version': '0.1.1-experimental',
                'base_zip_sha256': BASE_SHA, 'hardware_validated': False,
                'reason': 'Physical 0.1.0 logs show SDL mali/fb0 available; guessed GPU nodes caused premature exit',
                'changed_files': {n:digest(data) for n,data in replacements.items()}}
    replacements[PREFIX+'HOTFIX.json'] = (json.dumps(metadata, indent=2)+'\n').encode()
    with zipfile.ZipFile(BASE) as src:
        assert src.testzip() is None
        manifest = json.loads(src.read(PREFIX+'MANIFEST.json'))
        for name,data in replacements.items(): manifest['files'][name] = digest(data)
        manifest['hotfix'] = metadata['id']
        manifest['base_zip_sha256'] = BASE_SHA
        replacements[PREFIX+'MANIFEST.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
        # Never overwrite an existing artifact or the original 0.1.1 archive.
        with OUTPUT.open('xb') as f, zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
            for name in sorted(set(src.namelist()) | set(replacements)):
                if name in src.namelist(): info=src.getinfo(name)
                else:
                    info=zipfile.ZipInfo(name,(2026,1,1,0,0,0))
                    info.external_attr=0o100644<<16
                    info.compress_type=zipfile.ZIP_DEFLATED
                dst.writestr(info, replacements[name] if name in replacements else src.read(name))
    with zipfile.ZipFile(OUTPUT) as z:
        assert z.testzip() is None
        for name,sha in manifest['files'].items(): assert digest(z.read(name)) == sha, name
    sha=digest(OUTPUT.read_bytes())
    OUTPUT.with_suffix('.sha256').write_text(sha+'  '+OUTPUT.name+'\n')
    print(OUTPUT, 'bytes='+str(OUTPUT.stat().st_size), 'sha256='+sha)


if __name__ == '__main__': main()
