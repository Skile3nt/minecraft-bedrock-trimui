#!/usr/bin/env python3
"""Local, texture-only adaptation of Tal Melamed's selected pack; no game edits.

Requires host Pillow. Source comes exclusively from the author's MCPEDL link.
Generated artwork stays outside Git and is never bundled with the public port.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import uuid
import zipfile
from PIL import Image
from performance_profiles import load_jsonc

SOURCE_SHA = '2f80a202416bf7abd55d61bb5ed45a0dc8e1b1abcb088dc10dee770b772545e3'
SOURCE_URL = 'https://mcpedl.com/minecraft-classic-texture-pack/'
PACK_UUID = str(uuid.uuid5(uuid.UUID('cc23e01a-347e-11eb-adc1-0242ac120002'), 'trimui-1.16-textures-only-1'))
MODULE_UUID = str(uuid.uuid5(uuid.UUID(PACK_UUID), 'resources'))
VERSION = [1, 0, 1]
FOLDER = 'tal_melamed_classic_trimui_116'

def sha(data): return hashlib.sha256(data).hexdigest()
def encoded(value): return (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode()

def activate(existing):
    assert isinstance(existing, list)
    matches = [x for x in existing if x.get('pack_id') == PACK_UUID]
    assert not matches or matches == [{'pack_id':PACK_UUID,'version':VERSION}]
    # Existing packs, including No Particles, retain their relative priority.
    return existing if matches else [*existing, {'pack_id':PACK_UUID,'version':VERSION}]

def deactivate(existing):
    assert isinstance(existing, list)
    return [x for x in existing if x.get('pack_id') != PACK_UUID]

def build(source, assets, output):
    assert sha(source.read_bytes()) == SOURCE_SHA, 'Unexpected source archive'
    packs = sorted((assets/'resource_packs').glob('vanilla*'))
    assert packs and (assets/'resource_packs/vanilla/textures/terrain_texture.json').is_file()
    files = {}; skipped = {}; dimensions = {}
    def skip(path, reason): skipped[path] = reason
    with zipfile.ZipFile(source) as z:
        assert z.testzip() is None, 'Corrupt source ZIP'
        assert len(z.namelist()) == len(set(z.namelist())), 'Duplicate archive paths'
        for n in z.namelist():
            assert not Path(n).is_absolute() and '..' not in Path(n).parts
            assert (z.getinfo(n).external_attr >> 16) & 0o170000 != 0o120000
        prefix = 'Classic Texture Pack/'
        original = load_jsonc(z.read(prefix+'manifest.json').decode())
        assert original['header']['version'] == [1,0,0]
        assert original['header']['min_engine_version'] <= [1,16,221]
        assert original['modules'][0]['type'] == 'resources'
        for n in z.namelist():
            rel = n.removeprefix(prefix)
            if not rel.startswith(('textures/blocks/', 'textures/items/')) or not rel.endswith(('.png','.tga')):
                if not n.endswith('/'): skip(rel,'outside requested block/item textures')
                continue
            native = [p/rel for p in packs if (p/rel).is_file()]
            if not native: skip(rel,'no matching installed 1.16 path');continue
            if 'particle' in rel.lower() or 'bubble_column' in rel.lower():
                skip(rel,'particle-related image');continue
            data = z.read(n)
            with Image.open(io.BytesIO(data)) as im: im.load();size = im.size
            with Image.open(native[0]) as im: native_size = im.size
            if size != native_size: skip(rel,'UV/frame dimensions differ from installed 1.16');continue
            files[rel] = data; dimensions[rel] = list(size)
        atlas = load_jsonc(z.read(prefix+'textures/terrain_texture.json').decode())
        native_atlas = load_jsonc((assets/'resource_packs/vanilla/textures/terrain_texture.json').read_text())
        assert atlas['texture_name'] == native_atlas['texture_name'] == 'atlas.terrain'
        assert set(atlas['texture_data']) <= set(native_atlas['texture_data'])
        def references(value):
            if isinstance(value,str) and value.startswith('textures/'): yield value
            elif isinstance(value,dict):
                for v in value.values(): yield from references(v)
            elif isinstance(value,list):
                for v in value: yield from references(v)
        for path in references(atlas['texture_data']):
            assert any(path+ext in files or any((p/(path+ext)).is_file() for p in packs)
                       for ext in ('.png','.tga')), 'Missing atlas image: '+path
        for key in ('padding','num_mip_levels'):
            if key in native_atlas: atlas[key] = native_atlas[key]
        files['textures/terrain_texture.json'] = encoded(atlas)
        manifest = {'format_version':1,'header':{
            'name':'Classic Texture Pack - TrimUI 1.16',
            'description':'Tal Melamed; local block/item textures-only adaptation. Original source: MCPEDL.',
            'uuid':PACK_UUID,'version':VERSION,'min_engine_version':[1,16,0]},
            'modules':[{'type':'resources','uuid':MODULE_UUID,'version':VERSION}]}
        files['manifest.json'] = encoded(manifest)
        if prefix+'pack_icon.png' in z.namelist():
            icon = z.read(prefix+'pack_icon.png')
            with Image.open(io.BytesIO(icon)) as im: im.load()
            files['pack_icon.png'] = icon
    assert all(not p.startswith(('particles/','ui/','shaders/','sounds/','entity/','models/','animations/')) for p in files)
    assert len({p.casefold() for p in files}) == len(files), 'Case collision on FAT'
    for required in ('stone','dirt','grass_top','diamond_ore','planks_oak','water_still_grey','water_flow_grey','lava_still','lava_flow'):
        assert 'textures/blocks/'+required+'.png' in files, required
    with output.open('xb') as f, zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in sorted(files.items()): z.writestr(n,data)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert all(z.read(n) == b for n,b in files.items())
    return {'source':SOURCE_URL,'source_sha256':SOURCE_SHA,'source_version':original['header']['version'],
            'pack_uuid':PACK_UUID,'module_uuid':MODULE_UUID,'version':VERSION,'folder':FOLDER,
            'output_sha256':sha(output.read_bytes()),'files':{n:sha(b) for n,b in files.items()},
            'dimensions':dimensions,'excluded':skipped,'physical_validation':False,
            'scope':'Existing 1.16 block/item textures with identical native dimensions; no particle, UI, model, sound or shader overrides'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('assets',type=Path)
    parser.add_argument('output',type=Path);parser.add_argument('report',type=Path)
    a=parser.parse_args();report=build(a.source,a.assets,a.output);a.report.write_bytes(encoded(report))
    print('Validated',len(report['dimensions']),'images; UUID',PACK_UUID,'SHA256',report['output_sha256'])
