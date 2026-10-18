#!/usr/bin/env python3
"""Build the CrossMix prototype from pinned releases; no global installation."""
import argparse, hashlib, json, os, shutil, subprocess, tarfile, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT/'crossmix/ADAPTATION_VERSION').read_text().strip()
HOTFIX = 'performance-engineering-0.2.2'
STANDARD_HASH = 'a7a131cfca013fc38bebe8b0e810220f9df0a27b8f9a9f48d4ab508b8c527099'
WESTON_HASH = '0bccaeebc11296bb1fe4278c9677cb82965c5a04bcd63745fa09d78228bc1a93'
SOURCE_HASH = 'f757ec0d6c15409a1267ef2626dbda96b6e13245a6f49df32112be703a0c70b7'
BASE = 'https://github.com/DankMiimer/minecraft-bedrock-handheld-port/releases/download/v2.0.1/'


def previous_hardware_evidence():
    return {'version': '0.1.8-experimental',
            'launcher': 'user confirmed; physical menu opens',
            'controls': 'user confirmed in launcher',
            'diagnostics': 'user confirmed; device logs exit 0',
            'gpu': 'physical PowerVR GE8300 / OpenGL ES 3.2 / GL_ERROR=0x0 / exit 0',
            'weston_xwayland': 'physical listening and WM ready; temporary X11 directory mode 1777',
            'sdl_crusty_probe': 'physical auto/explicit: GLES 3.2, depth 24, stencil 8, GL_ERROR=0, swap=1; Xwayland not triggered by this minimal probe',
            'minecraft': 'user physically confirmed 3D gameplay, world creation/exploration, most gamepad controls; L2/R2 missing; performance poor'}


def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def fetch(cache, name, url, sha):
    target = cache / name
    if not target.exists():
        part = target.with_suffix(target.suffix + '.part')
        subprocess.run(['curl', '-fL', '--retry', '2', '--max-time', '120', url, '-o', str(part)], check=True)
        if digest(part) != sha: raise ValueError('Checksum mismatch: ' + name)
        part.replace(target)
    if digest(target) != sha: raise ValueError('Checksum mismatch: ' + name)
    return target


def safe_member(name):
    p = Path(name)
    return not p.is_absolute() and '..' not in p.parts


def unzip(source, dest):
    with zipfile.ZipFile(source) as z:
        if not all(safe_member(i.filename) for i in z.infolist()):
            raise ValueError('Unsafe upstream archive')
        z.extractall(dest)


def extract_deb(deb, dest):
    # bsdtar reads Debian ar and tar members without installing the package.
    names = subprocess.check_output(['bsdtar', '-tf', str(deb)], text=True).splitlines()
    data = next(n for n in names if n.startswith('data.tar.'))
    raw = subprocess.check_output(['bsdtar', '-xOf', str(deb), data])
    subprocess.run(['bsdtar', '-xf', '-', '-C', str(dest)], input=raw, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--downloads', type=Path, default=ROOT.parent/'downloads')
    parser.add_argument('--out', type=Path, default=ROOT/'dist')
    args = parser.parse_args()
    cache=args.downloads.resolve(); cache.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    standard=fetch(cache, 'minecraftbedrock-standard-v2.0.1.zip', BASE+'minecraftbedrock-standard-v2.0.1.zip', STANDARD_HASH)
    source=fetch(cache, 'minecraftbedrock-source-v2.0.1.zip', BASE+'minecraftbedrock-source-v2.0.1.zip', SOURCE_HASH)
    weston=fetch(cache, 'weston_pkg_0.2.aarch64.squashfs', 'https://raw.githubusercontent.com/PortsMaster/PortMaster-New/main/runtimes/weston_pkg_0.2.aarch64.squashfs', WESTON_HASH)
    stage=args.out/'stage'
    if stage.exists(): shutil.rmtree(stage)
    stage.mkdir()
    with tempfile.TemporaryDirectory(dir=args.out) as tmp:
        extracted=Path(tmp)/'upstream'; unzip(standard, extracted)
        game=stage/'Data/ports/minecraftbedrock'
        shutil.copytree(extracted/'ports/minecraftbedrock', game)
        shutil.rmtree(game/'bin32', ignore_errors=True)
        shutil.rmtree(game/'libs.armhf', ignore_errors=True)
        # The optional H700 downloader cannot run on A133; keep it out of this SKU.
        shutil.rmtree(game/'downloader', ignore_errors=True)
        adapter=game/'crossmix'; shutil.copytree(ROOT/'crossmix', adapter,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        upstream=ROOT/'portmaster/minecraftbedrock'
        for rel in ('lib/abi.sh','lib/common.sh','lib/platform.sh','run_bedrock.sh','weston_launch.sh','update_port.sh'):
            shutil.copyfile(upstream/'minecraftbedrock'/rel, game/rel)
        shutil.copyfile(upstream/'minecraftbedrock/failsafe_state.py', game/'failsafe_state.py')
        # Keep the launcher UI changes in this repository's source tree in the
        # packaged payload instead of silently reverting to the pinned archive.
        shutil.copyfile(upstream/'minecraftbedrock/menu/main.lua', game/'menu/main.lua')
        shutil.copyfile(upstream/'Minecraft Bedrock.sh', adapter/'upstream-entry.sh')
        shutil.copyfile(extracted/'ports/Minecraft Bedrock.sh', adapter/'upstream-entry.original.sh')
        for rel in ('run_bedrock.sh','weston_launch.sh','update_port.sh'):
            shutil.copyfile(extracted/'ports/minecraftbedrock'/rel, adapter/(rel+'.original'))
        # Reproducible local source and upstream corresponding-source materials.
        (adapter/'source').mkdir()
        shutil.copyfile(source, adapter/'source/upstream-source-v2.0.1.zip')
        (adapter/'source/integration.patch').write_bytes(subprocess.check_output(['git','diff','v2.0.1','--','portmaster','tests/test_performance.sh'],cwd=ROOT))
        runtime=adapter/'runtime'; runtime.mkdir()
        debian=runtime/'debian'; debian.mkdir()
        locks=json.loads((ROOT/'crossmix/debian-lock.json').read_text())
        for package in locks:
            deb=fetch(cache, Path(package['Filename']).name,
                package.get('URL','https://deb.debian.org/debian/'+package['Filename']), package['SHA256'])
            extract_deb(deb,debian)
        w=runtime/'weston'; w.mkdir()
        subprocess.run(['7z','x','-y','-o'+str(w), str(weston)],check=True,stdout=subprocess.DEVNULL)
        # A core dump and 32-bit runtime were shipped in the input; neither is needed.
        (w/'core').unlink(missing_ok=True)
        shutil.rmtree(w/'lib_armhf',ignore_errors=True)
        for p in (w/'lib_aarch64/graphics').iterdir():
            if p.name != 'crusty_x11egl': shutil.rmtree(p)
        subprocess.run(['aarch64-linux-gnu-gcc','-O2','-fPIC','-shared','-Wall','-Wextra',
            '-o',str(adapter/'isolate-crusty.so'),str(adapter/'isolate-crusty.c'),'-ldl'],check=True)
        subprocess.run(['aarch64-linux-gnu-gcc','-O2','-Wall','-Wextra','-o',str(adapter/'graphics-probe'),str(adapter/'graphics-probe.c'),'-ldl'],check=True)
        subprocess.run(['aarch64-linux-gnu-gcc','-O2','-fPIC','-shared','-Wall','-Wextra','-Werror',
            '-o',str(adapter/'sdl-trace.so'),str(adapter/'sdl-trace.c'),'-ldl'],check=True)
        subprocess.run(['aarch64-linux-gnu-gcc','-O2','-fPIC','-shared','-Wall','-Wextra','-Werror',
            '-o',str(adapter/'input-bridge.so'),str(adapter/'input-bridge.c'),'-ldl'],check=True)
        subprocess.run(['aarch64-linux-gnu-gcc','-O2','-fPIC','-shared','-nostdlib','-fno-builtin','-fno-stack-protector',
            '-Wall','-Wextra','-Werror','-o',str(adapter/'egl-bind-audit.so'),str(adapter/'egl-bind-audit.c')],check=True)
        subprocess.run(['aarch64-linux-gnu-gcc','-O2','-Wall','-Wextra','-Werror',
            '-o',str(adapter/'sdl-session-probe'),str(adapter/'sdl-session-probe.c'),'-ldl'],check=True)
        ports=stage/'Roms/PORTS'; ports.mkdir(parents=True)
        shutil.copyfile(adapter/'entry.sh',ports/'Minecraft Bedrock CrossMix.sh')
        for name, mode in [('Diagnostics', '--diagnose'), ('GPU Test', '--graphics-test'), ('SDL Test', '--sdl-test'), ('Input Test', '--input-test'), ('Original', '--original'), ('No Particles', '--no-particles'), ('Performance', '--performance'), ('No Particles Assets', '--no-particles-assets')]:
            (ports/('Minecraft Bedrock '+name+'.sh')).write_text(
                (adapter/'entry.sh').read_text().replace('entry_mode=${1:-}', 'entry_mode='+mode, 1))
        (game/'apk').mkdir(exist_ok=True)
        (game/'config').mkdir(exist_ok=True)
        shutil.copyfile(adapter/'performance-018.default.json',game/'config/performance-018.json')
        (game/'apk/PUT_LEGAL_APK_HERE.txt').write_text('Official owned Minecraft Bedrock 1.16.221.01, arm64-v8a; full APK or complete split set.\n')
        shutil.copyfile(adapter/'README.md',stage/'Minecraft-Bedrock-CrossMix-README.md')
        (adapter/'HOTFIX.json').write_text(json.dumps({'id':HOTFIX,'version':VERSION,'replaces':'sdl-egl-binding-diagnostics-1'},indent=2)+'\n')
        manifest={'adaptation':VERSION,'hotfix':HOTFIX,'hardware_tested':False,
            'previous_hardware_evidence': previous_hardware_evidence(),
            'upstream_standard_sha256':STANDARD_HASH,'upstream_source_sha256':SOURCE_HASH,
            'weston_sha256':WESTON_HASH,'debian_packages':locks,'files':{}}
        for p in sorted(stage.rglob('*')):
            if p.is_file():
                # Dereference ELF aliases for FAT/exFAT and reject outside-tree symlinks.
                if p.is_symlink():
                    resolved=p.resolve()
                    if not resolved.is_relative_to(stage.resolve()):
                        raise ValueError('External symlink in archive: '+str(p))
                    data=p.read_bytes();p.unlink();p.write_bytes(data)
                manifest['files'][p.relative_to(stage).as_posix()]=digest(p)
        (adapter/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
        output=args.out/('minecraft-bedrock-crossmix-'+VERSION+'.zip')
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(stage.rglob('*')):
                if not p.is_file(): continue
                rel=p.relative_to(stage).as_posix()
                if p.suffix.lower() in ('.apk','.apks','.xapk','.mcworld') or p.name=='libminecraftpe.so':
                    raise ValueError('Proprietary/user content in package: '+rel)
                info=zipfile.ZipInfo(rel,(2026,1,1,0,0,0))
                # Mark all ELF files executable, including ld-linux and runtime libraries.
                elf=p.open('rb').read(4)==b'\x7fELF'
                info.external_attr=((0o100755 if elf or p.suffix=='.sh' or p.parent==adapter/'bin' else 0o100644)<<16)
                info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,p.read_bytes())
        (args.out/'SHA256SUMS.txt').write_text(digest(output)+'  '+output.name+'\n')
        print(str(output.resolve()), 'bytes='+str(output.stat().st_size), 'sha256='+digest(output))


if __name__=='__main__': main()
