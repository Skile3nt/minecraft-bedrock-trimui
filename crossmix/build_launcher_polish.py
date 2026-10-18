#!/usr/bin/env python3
"""Reuse the verified rc1 payload/binaries; update only audited launcher scripts."""
import json
import subprocess
import zipfile
from pathlib import Path
import build_extreme_overlay as base

ROOT=base.ROOT
ORIGINAL=base.OUTPUT
ORIGINAL_SHA='c922435ebafe9404f1a4aa1e92db2b0e31f81360f466bd5a457e51b67dc9e55f'
OUTPUT=base.DIST/'Minecraft-Bedrock-TrimUI-1.0.0-rc1-Turquoise-r1.zip'

def payload():
    assert base.sha(ORIGINAL.read_bytes())==ORIGINAL_SHA
    with zipfile.ZipFile(ORIGINAL) as z:
        assert z.testzip() is None
        data={n:z.read(n) for n in z.namelist()}
    manifest=json.loads(data.pop(base.MANIFEST))
    assert all(base.sha(data[n])==h for n,h in manifest['files'].items())
    changed={
        'menu/main.lua':'portmaster/minecraftbedrock/minecraftbedrock/menu/main.lua',
        'menu/msgbox/main.lua':'portmaster/minecraftbedrock/minecraftbedrock/menu/msgbox/main.lua',
        'crossmix/performance_profiles.py':'crossmix/performance_profiles.py',
        'crossmix/session.sh':'crossmix/session.sh',
        'crossmix/entry.sh':'crossmix/entry.sh',
    }
    changed.update({n:n for n in ('PUBLIC_RELEASE.md','LAUNCHER_POLISH.md','CREDITS.md','AUTHORS.md','LEGAL.md','LICENSE')})
    for dest,src in changed.items():data[base.PREFIX+dest]=(ROOT/src).read_bytes()
    data['Roms/PORTS/Minecraft Bedrock Launcher.sh']=data[base.PREFIX+'crossmix/entry.sh'].replace(b'entry_mode=${1:-}',b'entry_mode=--finalize')
    manifest.update(revision='turquoise-r1',hardware_tested=False,
                    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    parent_archive_sha256=ORIGINAL_SHA,
                    installation_gate='Identify CrossMix card; back up changed destinations before installation.',
                    files={n:base.sha(b) for n,b in sorted(data.items())})
    data[base.MANIFEST]=(json.dumps(manifest,indent=2)+'\n').encode()
    return data

if __name__=='__main__':
    print(OUTPUT,base.write_archive(OUTPUT,payload()))
