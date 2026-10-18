#!/usr/bin/env python3
"""Reuse functional 0.1.8 binaries; fix inactive particle profiles and missing trigger mappings.

Only the two small adapter/observer modules are compiled. Upstream binaries
are preserved. Credentials, game data and APKs never enter this package.
"""
import hashlib
import json
import subprocess
from pathlib import Path
import zipfile
import build

C = Path(__file__).resolve().parent
BASE = C.parent/'dist/minecraft-bedrock-crossmix-0.1.8-experimental.zip'
BASE_SHA = '324954fa8e73c953df4e2445b7e0eacb8e84ed8a31c81bdd47276b09e65f5d8f'
PREFIX = 'Data/ports/minecraftbedrock/crossmix/'
OUTPUT = C.parent/f'dist/minecraft-bedrock-crossmix-{build.VERSION}.zip'


def sha(data): return hashlib.sha256(data).hexdigest()


def main():
    assert build.VERSION == '0.1.9-experimental'
    assert sha(BASE.read_bytes()) == BASE_SHA
    names = ('ADAPTATION_VERSION', 'session.sh', 'session_hotfix.py', 'build.py', 'README.md',
             'entry.sh', 'session_report.py', 'input-bridge.c', 'input-test.py',
             'performance_profiles.py', 'performance_profile_test.py',
             'particle-audit.c', 'particle_audit_test.py', 'trigger_mapping_test.py',
             'trimui.gamecontrollerdb.txt', 'HOTFIX_0.1.9.md')
    changes = {PREFIX+n: (C/n).read_bytes() for n in names}
    changes[PREFIX+'performance-018.default.json']=(C/'performance-018.default.json').read_bytes()
    changes['Data/ports/minecraftbedrock/config/performance-018.json']=(C/'performance-018.default.json').read_bytes()
    changes['Data/ports/minecraftbedrock/controls/trimui.gamecontrollerdb.txt']=(C/'trimui.gamecontrollerdb.txt').read_bytes()
    for source,output in [('input-bridge.c','input-bridge.so'),('particle-audit.c','particle-audit.so')]:
        binary=C.parent/'dist'/('019-'+output)
        subprocess.run(['aarch64-linux-gnu-gcc','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',str(C/source),
                        '-o',str(binary),'-ldl'],check=True)
        changes[PREFIX+output]=binary.read_bytes()
    for label,mode in [('CrossMix','${1:-}'),('Diagnostics','--diagnose'),('GPU Test','--graphics-test'),('SDL Test','--sdl-test'),('Input Test','--input-test'),('Original','--original'),('No Particles','--no-particles'),('Performance','--performance'),('No Particles Assets','--no-particles-assets')]:
        changes['Roms/PORTS/Minecraft Bedrock '+label+'.sh']=(C/'entry.sh').read_text().replace('entry_mode=${1:-}','entry_mode='+mode,1).encode()
    changes['Minecraft-Bedrock-CrossMix-README.md'] = (C/'README.md').read_bytes()
    metadata = {'id': build.HOTFIX, 'version': build.VERSION,
                'replaces': 'performance-pass-a-1', 'base_zip_sha256': BASE_SHA,
                'hardware_tested': False, 'reason': 'Enable reversible audited asset suppression instead of the inactive Original default; bounded particle file-open observer; exact-device trigger mapping from CrossMix SDL evidence; targeted physical capture; rendering/driver/client unchanged',
                'changed_files': {n: sha(data) for n, data in changes.items()}}
    changes[PREFIX+'HOTFIX.json'] = (json.dumps(metadata, indent=2)+'\n').encode()
    with zipfile.ZipFile(BASE) as src:
        assert src.testzip() is None
        manifest = json.loads(src.read(PREFIX+'MANIFEST.json'))
        manifest.update(adaptation=build.VERSION, hotfix=build.HOTFIX,
                        base_zip_sha256=BASE_SHA, hardware_tested=False,
                        previous_hardware_evidence=build.previous_hardware_evidence())
        for n, data in changes.items(): manifest['files'][n] = sha(data)
        changes[PREFIX+'MANIFEST.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
        with OUTPUT.open('xb') as out, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
            for name in sorted(set(src.namelist()) | set(changes)):
                info = src.getinfo(name) if name in src.namelist() else zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                if name not in src.namelist():
                    executable=name.endswith('.sh') or changes[name][:4]==b'\x7fELF'
                    info.external_attr = (0o100755 if executable else 0o100644) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                dst.writestr(info, changes[name] if name in changes else src.read(name))
        # Update local staging only for the tests, never from the device/game tree.
        for name, data in changes.items():
            p = C.parent/'dist/stage'/name
            p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    with zipfile.ZipFile(OUTPUT) as z:
        assert z.testzip() is None
        for n, digest in manifest['files'].items(): assert sha(z.read(n)) == digest, n
        assert not any(n.endswith(('.apk', '.apks', '/libminecraftpe.so')) for n in z.namelist())
    digest = sha(OUTPUT.read_bytes())
    OUTPUT.with_suffix('.sha256').write_text(digest+'  '+OUTPUT.name+'\n')
    print(OUTPUT, 'sha256='+digest)


if __name__ == '__main__': main()
