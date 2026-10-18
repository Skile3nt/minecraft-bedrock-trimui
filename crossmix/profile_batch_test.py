#!/usr/bin/env python3
"""Asset batch crash recovery, durability ordering and avoided journal I/O."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import performance_profiles as profiles
import performance_profile_test as fixtures


class LegacyManager(profiles.Manager):
    def edit_assets(self, changes):
        for path, content in changes:
            self.edit(path, content, 'asset')


class BatchTests(unittest.TestCase):
    def fixture(self, root, count=5, manager_class=profiles.Manager):
        m, asset, options = fixtures.Tests().fixture(root)
        m = manager_class(m.game, m.version, m.data)
        for index in range(count-1):
            value = fixtures.particle('minecraft:emitter_rate_instant', {'num_particles':30})
            value['particle_effect']['description']['identifier'] = f'minecraft:fixture{index}'
            asset.with_name(f'b{index:03}.json').write_text(json.dumps(value))
        originals = {p:p.read_bytes() for p in asset.parent.glob('*.json')}
        originals[options] = options.read_bytes()
        return m, originals

    def restored(self, manager, originals):
        profiles.Manager(manager.game, manager.version, manager.data).restore()
        self.assertFalse(manager.state_path.exists())
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content, str(path))

    def test_backup_failure_leaves_every_asset_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            manager, originals = self.fixture(root)
            real_sync = os.fsync
            def sync(fd):
                target = os.readlink(f'/proc/self/fd/{fd}')
                if '/backups/' in target and '/particles/' in target:
                    raise OSError('simulated backup flush failure')
                real_sync(fd)
            with patch.object(profiles.os, 'fsync', sync), self.assertRaises(OSError):
                manager.prepare('NO_PARTICLES', 'assets')
            for path, content in originals.items():
                if path.suffix == '.json': self.assertEqual(path.read_bytes(), content)
            self.restored(manager, originals)

    def test_before_intent_failure_has_no_asset_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            manager, originals = self.fixture(root)
            real_save = manager.save
            def save():
                if any(r['kind']=='asset' for r in manager.state['edits']):
                    raise RuntimeError('interrupted before batch intent')
                real_save()
            with patch.object(manager, 'save', save), self.assertRaises(RuntimeError):
                manager.prepare('NO_PARTICLES', 'assets')
            state = json.loads(manager.state_path.read_text())
            self.assertTrue(all(r['kind'] != 'asset' for r in state['edits']))
            for path, content in originals.items():
                if path.suffix == '.json': self.assertEqual(path.read_bytes(), content)
            self.restored(manager, originals)

    def test_durable_intent_before_first_replacement_recovers(self):
        with tempfile.TemporaryDirectory() as root:
            manager, originals = self.fixture(root)
            real_save = manager.save
            def save():
                real_save()
                if any(r['kind']=='asset' for r in manager.state['edits']):
                    raise RuntimeError('interrupted after durable batch intent')
            with patch.object(manager, 'save', save), self.assertRaises(RuntimeError):
                manager.prepare('NO_PARTICLES', 'assets')
            state = json.loads(manager.state_path.read_text())
            self.assertEqual(sum(r['kind']=='asset' for r in state['edits']), 5)
            self.restored(manager, originals)

    def test_partial_replacement_recovers_and_preserves_external_changes(self):
        for external_change in (False, True):
            with self.subTest(external_change=external_change), tempfile.TemporaryDirectory() as root:
                manager, originals = self.fixture(root)
                real_atomic = profiles.atomic
                replaced = []
                def atomic(path, content):
                    real_atomic(path, content)
                    if path in originals and path.suffix == '.json':
                        replaced.append(path)
                        if len(replaced)==3: raise RuntimeError('interrupted during batch')
                with patch.object(profiles, 'atomic', atomic), self.assertRaises(RuntimeError):
                    manager.prepare('NO_PARTICLES', 'assets')
                if external_change:
                    replaced[-1].write_bytes(b'external change')
                    with self.assertRaisesRegex(AssertionError, 'Changed particle asset'):
                        manager.restore()
                    self.assertEqual(replaced[-1].read_bytes(), b'external change')
                    self.assertTrue(manager.state_path.exists())
                else:
                    self.restored(manager, originals)

    def test_backup_ancestors_synced_before_intent(self):
        with tempfile.TemporaryDirectory() as root:
            manager, originals = self.fixture(root)
            synced = set()
            real_sync = os.fsync
            real_save = manager.save
            def sync(fd):
                real_sync(fd)
                synced.add(Path(os.readlink(f'/proc/self/fd/{fd}')))
            def save():
                for record in manager.state['edits']:
                    if record['kind'] != 'asset': continue
                    backup = manager.game/manager.state['backup']/record['path']
                    self.assertEqual(profiles.sha(backup.read_bytes()), record['before'])
                    self.assertIn(backup, synced)
                    directory = backup.parent
                    while directory.is_relative_to(manager.game):
                        self.assertIn(directory, synced)
                        if directory == manager.game: break
                        directory = directory.parent
                    self.assertEqual((manager.game/record['path']).read_bytes(), originals[manager.game/record['path']])
                real_save()
            with patch.object(profiles.os, 'fsync', sync), patch.object(manager, 'save', save):
                manager.prepare('NO_PARTICLES', 'assets')
            self.restored(manager, originals)

    def test_120_asset_operation_counts_and_identical_results(self):
        results = []
        for manager_class in (LegacyManager, profiles.Manager):
            with tempfile.TemporaryDirectory() as root:
                manager, originals = self.fixture(root, 120, manager_class)
                stats = {'fsync':0, 'journal_writes':0, 'journal_bytes':0}
                real_sync = os.fsync
                real_atomic = profiles.atomic
                def sync(fd):
                    stats['fsync'] += 1
                    real_sync(fd)
                def atomic(path, content):
                    if path == manager.state_path:
                        stats['journal_writes'] += 1
                        stats['journal_bytes'] += len(content)
                    real_atomic(path, content)
                with patch.object(profiles.os, 'fsync', sync), patch.object(profiles, 'atomic', atomic):
                    report = manager.prepare('PERFORMANCE', 'assets', 4, 40)
                contents = {p.relative_to(manager.game).as_posix():p.read_bytes() for p in originals}
                results.append((stats, report, contents))
                self.restored(manager, originals)
        before, after = results
        self.assertEqual(before[2], after[2])
        self.assertEqual(before[1]['patched'], after[1]['patched'])
        self.assertEqual(before[0]['journal_writes'], 122)
        self.assertEqual(after[0]['journal_writes'], 3)
        self.assertLess(after[0]['fsync'], before[0]['fsync']-200)
        self.assertLess(after[0]['journal_bytes'], before[0]['journal_bytes']/20)
        print('120 synthetic assets, host operation counts (not hardware timing):',
              json.dumps({'before':before[0], 'after':after[0]}))


if __name__ == '__main__': unittest.main()
