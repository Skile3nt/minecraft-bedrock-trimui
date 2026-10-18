#!/usr/bin/env python3
"""Install the verified final candidate onto the identified CrossMix card.

This tool is intentionally local-only: it does not package game content, and
it aborts before writes if identity, mount mode, archive hashes, or destinations
are not exactly what the final manifest describes.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CARD = Path('/run/media/skile/CROSSMIXOS')
ZIP = ROOT/'dist/Minecraft-Bedrock-TrimUI-1.0.0-rc1-Final-Candidate-r3.zip'
ZIP_SHA256 = 'c922435ebafe9404f1a4aa1e92db2b0e31f81360f466bd5a457e51b67dc9e55f'
UUID = '1B16-2B5A'
SERIAL = '1c000c660500c8d251d'
PREFIX = 'Data/ports/minecraftbedrock/'


def sha_bytes(data): return hashlib.sha256(data).hexdigest()
def sha_file(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def command(args): return subprocess.check_output(args, text=True, timeout=15)


def identity():
    tree = json.loads(command(['lsblk', '-J', '-o', 'NAME,PATH,TYPE,TRAN,MODEL,SERIAL,FSTYPE,LABEL,UUID,MOUNTPOINTS']))
    disks = [d for d in tree['blockdevices'] if d.get('tran') == 'usb' and d.get('serial') == SERIAL and d.get('model', '').strip() == 'TRIMUI ADB']
    assert len(disks) == 1, 'TrimUI serial/model is not unique'
    parts = [p for p in disks[0].get('children', []) if p.get('uuid') == UUID and p.get('label') == 'CROSSMIXOS' and p.get('fstype') == 'vfat']
    assert len(parts) == 1, 'CROSSMIXOS FAT partition is not unique'
    mount = json.loads(command(['findmnt', '-J', '-S', parts[0]['path'], '-o', 'SOURCE,FSTYPE,OPTIONS,TARGET']))['filesystems']
    assert len(mount) == 1 and mount[0]['target'] == str(CARD) and mount[0]['fstype'] == 'vfat', 'unexpected mount target'
    assert 'rw' in mount[0]['options'].split(','), 'card is not mounted read/write'
    for relative in ('Roms/PORTS', 'Imgs/PORTS', 'Data/ports/minecraftbedrock'):
        assert (CARD/relative).is_dir(), 'missing CrossMix path: '+relative
    return parts[0]['path']


def safe_destination(name):
    path = Path(name)
    assert not path.is_absolute() and '..' not in path.parts
    assert name.startswith(PREFIX) or name in ('Roms/PORTS/Minecraft Bedrock Launcher.sh', 'Imgs/PORTS/Minecraft Bedrock Launcher.png')
    dest = CARD/path
    assert dest.parent.resolve().is_relative_to(CARD.resolve()), 'destination escapes card'
    if dest.exists(): assert dest.is_file() and not dest.is_symlink(), 'unexpected destination: '+name
    return dest


def atomic_write(path, data, executable):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.mcpe-final.tmp')
    assert not temporary.exists(), 'stale temporary file: '+str(temporary)
    with temporary.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.chmod(temporary, 0o755 if executable else 0o644)
    assert sha_file(temporary) == sha_bytes(data), 'temporary hash mismatch'
    os.replace(temporary, path)
    assert sha_file(path) == sha_bytes(data), 'installed hash mismatch'


def backup_existing(path, backup_root, name):
    if not path.exists(): return None
    saved = backup_root/'files'/name
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, saved)
    assert sha_file(saved) == sha_file(path), 'backup hash mismatch: '+name
    return sha_file(saved)


def main():
    assert sha_file(ZIP) == ZIP_SHA256, 'final candidate SHA-256 mismatch'
    identity()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    game = CARD/'Data/ports/minecraftbedrock'
    backup = game/'backups'/('final-install-'+stamp)
    backup.mkdir(mode=0o700)
    with zipfile.ZipFile(ZIP) as archive:
        assert archive.testzip() is None, 'ZIP CRC failure'
        data = {item.filename: archive.read(item) for item in archive.infolist() if not item.is_dir()}
        manifest = json.loads(data[PREFIX+'crossmix/FINAL_CANDIDATE_MANIFEST.json'])
        assert manifest['version'] == '1.0.0-rc1'
        expected = manifest['files']
        assert set(expected) | {PREFIX+'crossmix/FINAL_CANDIDATE_MANIFEST.json'} == set(data), 'unexpected ZIP member'
        for name, digest in expected.items(): assert sha_bytes(data[name]) == digest, 'ZIP hash mismatch: '+name
        manifest_name = PREFIX+'crossmix/FINAL_CANDIDATE_MANIFEST.json'
        install_hashes = dict(expected)
        install_hashes[manifest_name] = sha_bytes(data[manifest_name])
        records = {}
        for name in sorted(install_hashes):
            dest = safe_destination(name)
            records[name] = {'before': backup_existing(dest, backup, name), 'after': install_hashes[name]}
        (backup/'install-plan.json').write_text(json.dumps({'archive': ZIP.name, 'archive_sha256': ZIP_SHA256, 'files': records}, indent=2)+'\n')
        for name in sorted(expected):
            atomic_write(safe_destination(name), data[name], name.endswith(('.sh', '.so')))
        # Preserve the manifest itself with the same atomic/hashing discipline.
        atomic_write(safe_destination(manifest_name), data[manifest_name], False)
    # Cleanup is now performed during install, not deferred to a first launch.
    subprocess.run(['python3', str(game/'crossmix/cleanup_menu.py'), str(CARD/'Roms/PORTS'), str(game)], check=True)
    for name, record in records.items():
        assert sha_file(safe_destination(name)) == record['after'], 'post-install hash mismatch: '+name
    assert (CARD/'Roms/PORTS/Minecraft Bedrock Launcher.sh').is_file()
    assert (CARD/'Imgs/PORTS/Minecraft Bedrock Launcher.png').is_file()
    legacy = json.loads((game/'config/final-menu-cleanup.json').read_text())['moved']
    assert len(legacy) == 9, 'unexpected legacy menu cleanup result'
    for item in legacy: assert not (CARD/'Roms/PORTS'/item['name']).exists()
    os.sync()
    print(json.dumps({'installed': True, 'backup': str(backup), 'files': len(records),
                      'legacy_entries_moved': len(legacy), 'save_tree_untouched': True}, indent=2))


if __name__ == '__main__': main()
