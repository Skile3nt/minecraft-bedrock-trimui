#!/usr/bin/env python3
"""Host installer/rollback: strict payload hashes, only changed files, no user data."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import zipfile
import install_final_candidate as previous

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'dist/Minecraft-Bedrock-TrimUI-1.0.0-rc1-Turquoise-r1.zip'
MANIFEST=previous.PREFIX+'crossmix/FINAL_CANDIDATE_MANIFEST.json'

def payload(archive):
    expected=archive.with_suffix(archive.suffix+'.sha256').read_text().split()[0]
    assert previous.sha_file(archive)==expected
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        data={i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
    manifest=json.loads(data[MANIFEST]); assert manifest['revision']=='turquoise-r1'
    assert set(data)==set(manifest['files'])|{MANIFEST}
    for name,h in manifest['files'].items():assert previous.sha_bytes(data[name])==h
    for name in data:
        rel=name.removeprefix(previous.PREFIX)
        assert not rel.startswith(('config/','profiles/','versions/','apk/','controls/','backups/','logs/'))
        previous.safe_destination(name)
    return data

def apply(data,backup):
    changed={n:b for n,b in data.items() if not previous.safe_destination(n).exists() or
             previous.sha_file(previous.safe_destination(n))!=previous.sha_bytes(b)}
    backup.mkdir(parents=True,exist_ok=False)
    records={}
    for n,b in changed.items():
        before=previous.backup_existing(previous.safe_destination(n),backup,n)
        records[n]={'before':before,'after':previous.sha_bytes(b)}
    previous.atomic_write(backup/'install-plan.json',(json.dumps({'files':records},indent=2)+'\n').encode(),False)
    for n,b in changed.items():previous.atomic_write(previous.safe_destination(n),b,n.endswith(('.sh','.so')))
    for n,b in data.items():assert previous.sha_file(previous.safe_destination(n))==previous.sha_bytes(b)
    return len(changed)

def rollback(backup):
    assert backup.resolve().is_relative_to(previous.CARD/'Data/ports/minecraftbedrock/backups')
    records=json.loads((backup/'install-plan.json').read_text())['files']
    # Preflight every target and saved original before changing anything.
    for n,r in records.items():
        rel=n.removeprefix(previous.PREFIX)
        assert not rel.startswith(('config/','profiles/','versions/','apk/','controls/','backups/','logs/'))
        target=previous.safe_destination(n)
        current=previous.sha_file(target) if target.exists() else None
        assert current in (r['after'],r['before']), 'Changed since update: '+n
        if r['before'] is not None:assert previous.sha_file(backup/'files'/n)==r['before']
    for n,r in records.items():
        target=previous.safe_destination(n)
        if r['before'] is None:target.unlink(missing_ok=True)
        else:previous.atomic_write(target,(backup/'files'/n).read_bytes(),n.endswith(('.sh','.so')))
    previous.os.sync()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--rollback',type=Path)
    args=parser.parse_args();previous.identity()
    if args.rollback:
        rollback(args.rollback);print('ROLLBACK VERIFIED')
    else:
        data=payload(PACKAGE)
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=previous.CARD/'Data/ports/minecraftbedrock/backups'/('launcher-polish-'+stamp)
        count=apply(data,backup);previous.os.sync()
        print(json.dumps({'changed_files':count,'backup':str(backup),'all_payload_hashes':'verified'}))
