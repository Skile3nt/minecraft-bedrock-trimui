#!/usr/bin/env python3
"""Structural 1.16 fixture tests, journal recovery, provenance and byte rollback."""
import json
from pathlib import Path
import tempfile
import unittest
from performance_profiles import Manager, neutralize, load_jsonc, PACK_ID


def particle(rate, fields):
    return {'format_version':'1.10.0','particle_effect':{
        'description':{'identifier':'minecraft:fixture','basic_render_parameters':{'texture':'textures/particle/particles'}},
        'components':{rate:fields,'minecraft:particle_lifetime_expression':{'max_lifetime':3}}}}


class Tests(unittest.TestCase):
    def test_three_rates_and_original_unchanged(self):
        for rate,field in [('instant','num_particles'),('steady','spawn_rate'),('manual','max_particles')]:
            orig=particle('minecraft:emitter_rate_'+rate,{field:10})
            result,skip=neutralize(orig)
            self.assertIsNone(skip);self.assertEqual(result['particle_effect']['components']['minecraft:emitter_rate_'+rate][field],0)
            self.assertEqual(orig['particle_effect']['components']['minecraft:emitter_rate_'+rate][field],10)
            self.assertEqual(result['particle_effect']['description'],orig['particle_effect']['description'])

    def test_jsonc_does_not_corrupt_molang_or_urls(self):
        self.assertEqual(load_jsonc('{"x":"http://a/*b*/",// comment\n"y":[1,],}'),{'x':'http://a/*b*/','y':[1]})

    def test_sound_sensitive_effect_preserved(self):
        x=particle('minecraft:emitter_rate_manual',{'max_particles':10})
        x['particle_effect']['events']={'sound':{'sound_effect':{'event_name':'drip'}}}
        result,reason=neutralize(x);self.assertEqual(result,x);self.assertIn('sound',reason)
        x['particle_effect']['components']['minecraft:particle_appearance_billboard']={'size':[.15,.15]}
        result,reason=neutralize(x)
        self.assertIsNone(reason)
        self.assertEqual(result['particle_effect']['events'],x['particle_effect']['events'])
        self.assertEqual(result['particle_effect']['components']['minecraft:emitter_rate_manual'],{'max_particles':10})
        self.assertEqual(result['particle_effect']['components']['minecraft:particle_appearance_billboard']['size'],[0,0])

    def fixture(self, temp):
        g=Path(temp);v='1.16.221.01-971622101-arm64';data=g/'profiles'/v/'mcpelauncher'
        (g/'logs').mkdir();asset=g/'versions'/v/'assets/resource_packs/vanilla/particles/a.json'
        asset.parent.mkdir(parents=True);asset.write_text(json.dumps(particle('minecraft:emitter_rate_instant',{'num_particles':30})))
        opt=data/'games/com.mojang/minecraftpe/options.txt';opt.parent.mkdir(parents=True)
        opt.write_text('gfx_fancygraphics:1\ngfx_msaa:1\ngfx_bubble_particles:1\ngfx_multithreaded_renderer:1\ngfx_async_texture_loads:1\ngfx_viewdistance:80\ngfx_max_dequeued_textures_per_frame:8\ngfx_max_framerate:30\nmp_username:private\n')
        return Manager(g,v,data),asset,opt

    def test_pack_options_and_non_owned_preferences_restored(self):
        with tempfile.TemporaryDirectory() as t:
            m,asset,opt=self.fixture(t);before=asset.read_bytes();original=opt.read_bytes()
            r=m.prepare('PERFORMANCE','pack');self.assertEqual(r['requested_render_size'],[1024,576])
            self.assertEqual(asset.read_bytes(),before);self.assertIn('gfx_fancygraphics:0',opt.read_text())
            self.assertIn('gfx_multithreaded_renderer:1',opt.read_text());self.assertNotIn('gfx_toggleclouds',opt.read_text())
            self.assertIn('gfx_max_dequeued_textures_per_frame:8',opt.read_text())
            global_packs=m.data/'games/com.mojang/global_resource_packs.json'
            self.assertEqual(json.loads(global_packs.read_text())[0]['pack_id'],PACK_ID)
            # Simulate an unrelated preference changed by the game: retain it.
            opt.write_text(opt.read_text().replace('mp_username:private','mp_username:changed'))
            m.restore();self.assertEqual(opt.read_bytes(),original.replace(b'private',b'changed'))
            self.assertFalse(global_packs.exists());self.assertFalse(m.state_path.exists())
            m.prepare('ORIGINAL');self.assertEqual(asset.read_bytes(),before)

    def test_asset_fallback_hash_rollback_and_killed_session_recovery(self):
        with tempfile.TemporaryDirectory() as t:
            m,asset,opt=self.fixture(t);original=asset.read_bytes();options=opt.read_bytes()
            m.prepare('NO_PARTICLES','assets');self.assertNotEqual(asset.read_bytes(),original)
            # New process recovers pending edits before choosing ORIGINAL.
            Manager(m.game,m.version,m.data).prepare('ORIGINAL')
            self.assertEqual(asset.read_bytes(),original);self.assertEqual(opt.read_bytes(),options)

    def test_modified_asset_refuses_destructive_restore(self):
        with tempfile.TemporaryDirectory() as t:
            m,asset,opt=self.fixture(t);m.prepare('NO_PARTICLES','assets');asset.write_text('modified externally')
            with self.assertRaises(AssertionError):m.restore()
            self.assertEqual(asset.read_text(),'modified externally');self.assertTrue(m.state_path.exists())

    def test_other_resource_packs_survive(self):
        with tempfile.TemporaryDirectory() as t:
            m,asset,opt=self.fixture(t);p=m.data/'games/com.mojang/global_resource_packs.json'
            original=b'[ {"pack_id":"other", "version":[1,0,0]} ]\n';p.write_bytes(original)
            m.prepare('NO_PARTICLES','pack');m.restore();self.assertEqual(p.read_bytes(),original)

    def test_performance_fps_caps_are_temporary_and_isolated(self):
        for cap in (30, 40, 50):
            with self.subTest(cap=cap), tempfile.TemporaryDirectory() as t:
                m,asset,opt=self.fixture(t);original=opt.read_bytes()
                report=m.prepare('PERFORMANCE','assets',4,cap)
                self.assertEqual(report['fps_cap_requested'],cap)
                self.assertEqual(report['options']['gfx_max_framerate'],
                                 {'original':'30','applied':str(cap)})
                self.assertIn(f'gfx_max_framerate:{cap}',opt.read_text())
                m.restore();self.assertEqual(opt.read_bytes(),original)

    def test_fps_experiment_does_not_touch_other_profiles_or_unknown_options(self):
        for profile in ('ORIGINAL','NO_PARTICLES'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as t:
                m,asset,opt=self.fixture(t);original=opt.read_bytes()
                m.prepare(profile,'assets',4,50)
                self.assertIn('gfx_max_framerate:30',opt.read_text())
                if profile=='ORIGINAL': self.assertEqual(opt.read_bytes(),original)
                m.restore();self.assertEqual(opt.read_bytes(),original)
        with tempfile.TemporaryDirectory() as t:
            m,asset,opt=self.fixture(t);opt.write_text(opt.read_text().replace('gfx_max_framerate:30\n',''))
            before=opt.read_bytes()
            with self.assertRaisesRegex(AssertionError,'lack gfx_max_framerate'):
                m.prepare('PERFORMANCE','assets',4,40)
            self.assertEqual(opt.read_bytes(),before)

    def test_original_does_not_block_other_launcher_versions(self):
        with tempfile.TemporaryDirectory() as t:
            m,asset,opt=self.fixture(t)
            other=Manager(m.game,'different-version',m.data)
            self.assertEqual(other.prepare('ORIGINAL')['profile'],'ORIGINAL')
            with self.assertRaises(AssertionError):other.prepare('PERFORMANCE')


if __name__=='__main__':unittest.main()
