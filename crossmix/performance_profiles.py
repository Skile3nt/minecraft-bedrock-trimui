#!/usr/bin/env python3
"""0.1.8 opt-in profiles. Local licensed assets only; journaled, reversible edits.

0.1.9 uses the journaled local asset path by default. Pack mode remains opt-in.
"""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import uuid

PACK_ID = '3f5e6410-237d-4c71-bd4e-4e06c4110018'
RATES = {'minecraft:emitter_rate_instant': ('num_particles',),
         'minecraft:emitter_rate_steady': ('spawn_rate', 'max_particles'),
         'minecraft:emitter_rate_manual': ('max_particles',)}
LOW = dict.fromkeys(['gfx_fancygraphics', 'gfx_fancyskies', 'gfx_toggleclouds',
                    'gfx_smoothlighting', 'gfx_transparentleaves', 'gfx_texel_aa_2',
                    'gfx_viewbobbing', 'screen_animations', 'camera_shake'], '0')
PARTICLE_OPTIONS = {'gfx_particleviewdistance': '0', 'gfx_bubble_particles': '0'}


def sha(data): return hashlib.sha256(data).hexdigest()


def load_jsonc(text):
    # Bedrock 1.16 vanilla uses comments/trailing commas. Preserve quoted Molang.
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/|,\s*(?=[}\]])')
    clean = tokens.sub(lambda m: m[0] if m[0].startswith('"') else
                       '' if m[0].startswith(',') else ' ', text)
    return json.loads(clean)


def neutralize(data):
    result = copy.deepcopy(data)
    effect = result['particle_effect']; components = effect['components']
    assert data['format_version'] == '1.10.0', 'Unreviewed particle format'
    assert isinstance(effect['description']['identifier'], str)
    if '"sound_effect"' in json.dumps(effect):
        billboard = components.get('minecraft:particle_appearance_billboard')
        if billboard is None: return result, 'preserve particle-triggered sound'
        # Honey's collision triggers audio: retain its simulation, hide its quad.
        billboard['size'] = [0, 0]
        return result, None
    found = False
    for rate, fields in RATES.items():
        if rate in components:
            assert isinstance(components[rate], dict)
            for field in fields: components[rate][field] = 0
            found = True
    return result, None if found else 'unrecognized emitter rate'


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.is_symlink(), 'Refuse symlink target'
    tmp = path.with_name(path.name+'.018-'+str(os.getpid())+'.tmp')
    with tmp.open('xb') as f: f.write(data);f.flush();os.fsync(f.fileno())
    assert sha(tmp.read_bytes()) == sha(data)
    os.replace(tmp, path)
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)


def encoded(value): return (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode()


class Manager:
    def __init__(self, game, version, data):
        self.game = Path(game).resolve(); self.version = version
        assert '/' not in version and version not in ('.','..'), 'Invalid version path'
        self.data = Path(data).resolve()
        assert self.data.is_relative_to(self.game/'profiles'), 'Data must be this port profile'
        self.assets = self.game/'versions'/version/'assets'
        self.state_path = self.game/'config/performance-018-state.json'
        self.state = None

    def save(self): atomic(self.state_path, encoded(self.state))

    def edit(self, path, content, kind, **metadata):
        path = path.resolve(); assert path.is_relative_to(self.game)
        current = path.read_bytes() if path.exists() else None
        if current == content: return
        relative = path.relative_to(self.game).as_posix()
        backup = self.game/self.state['backup']/relative
        if current is not None:
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open('xb') as f:f.write(current);f.flush();os.fsync(f.fileno())
            assert sha(backup.read_bytes()) == sha(current)
        self.state['edits'].append(dict(path=relative, kind=kind, before=sha(current) if current is not None else None,
                                       after=sha(content), **metadata))
        self.save()  # intent is durable BEFORE replacement
        atomic(path, content)

    def edit_assets(self, changes):
        """Publish one durable intent for the asset batch before replacing any asset.

        The existing restore handles an unapplied record (current == backup), so
        a partial batch needs no new journal format or rollback procedure.
        """
        pending = []
        directories = set()
        for path, content in changes:
            path = path.resolve(); assert path.is_relative_to(self.game)
            current = path.read_bytes()
            if current == content: continue
            relative = path.relative_to(self.game).as_posix()
            backup = self.game/self.state['backup']/relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open('xb') as f:
                f.write(current); f.flush(); os.fsync(f.fileno())
            assert sha(backup.read_bytes()) == sha(current)
            # mkdir(parents=True) may create several levels. Persist their
            # entries too, not just the directory containing the backup file.
            directory = backup.parent
            while directory.is_relative_to(self.game):
                directories.add(directory)
                if directory == self.game: break
                directory = directory.parent
            record = dict(path=relative, kind='asset', before=sha(current), after=sha(content))
            pending.append((path, content, record))
        if not pending: return
        for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
            fd = os.open(directory, os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        self.state['edits'].extend(record for _, _, record in pending)
        self.save()  # all backup data/entries durable; no asset changed yet
        for path, content, record in pending:
            assert sha(path.read_bytes()) == record['before'], 'Asset changed during preparation; refusing overwrite'
            atomic(path, content)

    def restore(self):
        if not self.state_path.exists(): return
        self.state = json.loads(self.state_path.read_text())
        for record in reversed(self.state['edits']):
            path = self.game/record['path']; assert path.resolve().is_relative_to(self.game)
            backup = self.game/self.state['backup']/record['path']
            old = backup.read_bytes() if record['before'] is not None else None
            assert old is None or sha(old) == record['before'], 'Backup integrity failure'
            current = path.read_bytes() if path.exists() else None
            if current == old: continue  # interrupted before edit, or already restored
            if record['kind'] == 'options':
                assert current is not None
                if sha(current)==record['after']:
                    atomic(path, old);continue
                lines = current.decode().splitlines(keepends=True)
                for i, line in enumerate(lines):
                    key, sep, value = line.rstrip('\r\n').partition(':')
                    if sep and key in record['keys'] and value == record['keys'][key]['applied']:
                        lines[i] = key+':'+record['keys'][key]['original']+'\n'
                atomic(path, ''.join(lines).encode())
            elif record['kind'] == 'pack-list':
                packs = json.loads(current or b'[]')
                assert isinstance(packs, list)
                packs = [p for p in packs if p.get('pack_id') != PACK_ID]
                if old is None and not packs: path.unlink(missing_ok=True)
                elif packs == json.loads(old or b'[]') and old is not None: atomic(path, old)
                else: atomic(path, encoded(packs))
            else:
                assert current is not None and sha(current) == record['after'], 'Changed particle asset; refusing overwrite'
                assert old is not None
                atomic(path, old)
        # Retain history/backups; removing the journal only follows full restore.
        atomic(self.game/self.state['backup']/'RESTORED.json', encoded({'restored':True, 'profile':self.state['profile']}))
        self.state_path.unlink()

    def prepare(self, profile, method='assets', streaming=None, fps_cap=None):
        assert profile in ['ORIGINAL', 'NO_PARTICLES', 'PERFORMANCE']
        assert method in ['pack', 'assets']
        if fps_cap is not None:
            assert type(fps_cap) is int and fps_cap in [30, 40, 50], 'Performance FPS cap must be 30, 40 or 50'
        self.restore()  # recovery from a killed previous run
        report = {'profile':profile, 'particle_method':method, 'patched':[], 'skipped':[],
                  'resource_pack_override':'requires physical verification', 'options':{},
                  'requested_render_size':[1024,576] if profile=='PERFORMANCE' else [1280,720],
                  'effective_render_size':'not yet observed'}
        if profile == 'ORIGINAL':
            atomic(self.game/'logs/crossmix-profile-018.json',encoded(report));return report
        assert self.version == '1.16.221.01-971622101-arm64', 'Optimization only supports audited 1.16 release; choose Original'
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        backup = self.game/'backups/performance-018'/stamp;backup.mkdir(parents=True)
        self.state = {'profile':profile,'backup':backup.relative_to(self.game).as_posix(),'edits':[]};self.save()
        option = self.data/'games/com.mojang/minecraftpe/options.txt'
        assert option.is_file(), 'Existing 1.16 options required; no preferences invented'
        lines = option.read_text().splitlines(keepends=True)
        values = dict(PARTICLE_OPTIONS)
        if profile == 'PERFORMANCE':
            values.update(LOW);values['gfx_msaa']='1'  # observed no multisample buffers, 1=one sample
            if streaming is not None:
                assert streaming in [8,4,2]; values['gfx_max_dequeued_textures_per_frame']=str(streaming)
            if fps_cap is not None:
                values['gfx_max_framerate']=str(fps_cap)
        keys = {}
        for i, line in enumerate(lines):
            key, sep, original = line.rstrip('\r\n').partition(':')
            if sep and key in values:
                keys[key]={'original':original,'applied':values[key]}
                lines[i]=key+':'+values[key]+'\n'
        if profile == 'PERFORMANCE' and fps_cap is not None:
            assert 'gfx_max_framerate' in keys, 'Audited Minecraft options lack gfx_max_framerate; refusing FPS experiment'
        self.edit(option, ''.join(lines).encode(), 'options', keys=keys);report['options']=keys
        if profile == 'PERFORMANCE':
            report['fps_cap_requested'] = fps_cap if fps_cap is not None else 'unchanged'
        files = list((self.assets/'resource_packs').glob('*/particles/*.json'))
        assert files, 'No local particle definitions'
        selected = {}
        asset_changes = []
        def order(path):
            match=re.fullmatch(r'vanilla_(\d+)\.(\d+)(?:\.(\d+))?',path.parent.parent.name)
            return tuple(map(int,match.groups(default='0'))) if match else (0,0,0)
        for path in sorted(files, key=order):
            source = load_jsonc(path.read_text()); modified, skip = neutralize(source)
            ident = source['particle_effect']['description']['identifier']
            if skip:
                report['skipped'].append({'identifier':ident,'reason':skip}); continue
            sound = '"sound_effect"' in json.dumps(source['particle_effect'])
            report['patched'].append({'path':path.relative_to(self.assets).as_posix(), 'identifier':ident,
                                      'treatment':'hidden; simulation/audio retained' if sound else 'zero emission budget',
                                      'original_sha256':sha(path.read_bytes()), 'patched_sha256':sha(encoded(modified))})
            selected[ident] = (modified,path.name)
            if method == 'assets': asset_changes.append((path, encoded(modified)))
        if method == 'assets': self.edit_assets(asset_changes)
        if method == 'pack':
            pack = self.data/'games/com.mojang/resource_packs/trimui_no_particles_018'
            pack.mkdir(parents=True, exist_ok=True)
            manifest = {'format_version':2, 'header':{'name':'TrimUI No Particles 0.1.8',
                'description':'Local emission suppression; honey drip sound retained.', 'uuid':PACK_ID,
                'version':[0,1,8], 'min_engine_version':[1,16,0]},
                'modules':[{'type':'resources','uuid':str(uuid.uuid5(uuid.UUID(PACK_ID),'resources')),'version':[0,1,8]}]}
            for ident, (value,filename) in selected.items():
                dest=pack/'particles'/filename
                content=encoded(value)
                if not dest.exists(): atomic(dest, content)
                else: assert dest.read_bytes()==content, 'Generated pack modified; refusing overwrite'
            if not (pack/'manifest.json').exists(): atomic(pack/'manifest.json', encoded(manifest))
            else: assert json.loads((pack/'manifest.json').read_text())==manifest
            global_packs=self.data/'games/com.mojang/global_resource_packs.json'
            packs=json.loads(global_packs.read_text()) if global_packs.exists() else []
            assert isinstance(packs,list) and not any(p.get('pack_id')==PACK_ID for p in packs)
            self.edit(global_packs, encoded([{'pack_id':PACK_ID,'version':[0,1,8]},*packs]), 'pack-list')
        report['unique_overrides']=len(selected)
        if method == 'assets':
            for record in report['patched']:
                path = self.assets/record['path']
                assert sha(path.read_bytes()) == record['patched_sha256'], 'Active asset hash mismatch'
                assert load_jsonc(path.read_text())['particle_effect']['description']['identifier'] == record['identifier']
            report['active_assets_root'] = str(self.assets)
            report['active_asset_hashes_verified'] = True
        report['engine_acceptance'] = 'unconfirmed; inspect crossmix-particle-audit.log and physical effects'
        report['note']='Zero emission budgets; engine acceptance/actual savings not yet physically validated. Native hardcoded particles may remain.'
        atomic(self.game/'logs/crossmix-profile-018.json',encoded(report))
        return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','restore'])
    parser.add_argument('--game',default=os.environ.get('GAMEDIR'));parser.add_argument('--version',default=os.environ.get('MCVER_OVERRIDE'))
    parser.add_argument('--data',default=os.environ.get('MCPELAUNCHER_DATA_DIR'))
    args=parser.parse_args();manager=Manager(args.game,args.version,args.data)
    if args.action=='restore': manager.restore();return
    cfg=manager.game/'config/performance-018.json'
    settings=json.loads(cfg.read_text()) if cfg.exists() else {}
    profile=os.environ.get('MCPE_PERF_PROFILE',settings.get('profile','NO_PARTICLES'))
    cap=os.environ.get('MCPE_PERF_FPS_CAP',settings.get('performance_fps_cap',30))
    if isinstance(cap,str) and cap.isdigit():
        cap=int(cap)
    if type(cap) is not int or cap not in [30,40,50]:
        print('invalid performance_fps_cap; using safe baseline 30',file=__import__('sys').stderr)
        cap=30
    failsafe_rung=os.environ.get('MCPE_FAILSAFE_RUNG','0')
    apply_cap=profile=='PERFORMANCE' and failsafe_rung in ('','0')
    report=manager.prepare(profile,os.environ.get('MCPE_PARTICLE_METHOD',settings.get('particles_method','assets')),
                           settings.get('texture_dequeue'),cap if apply_cap else None)
    w,h=report['requested_render_size']
    for key,value in {'MCPE_PERF_PROFILE_ACTIVE':profile,'MCPE_RENDER_WIDTH':str(w),'MCPE_RENDER_HEIGHT':str(h)}.items():
        print('export '+key+'='+shlex.quote(value))
    if profile=='PERFORMANCE':
        active_cap=str(cap) if apply_cap else 'failsafe-managed'
        print('export MCPE_PERF_FPS_CAP_ACTIVE='+shlex.quote(active_cap))


if __name__=='__main__':main()
