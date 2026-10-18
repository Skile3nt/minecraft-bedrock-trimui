#!/usr/bin/env python3
"""Package contract and cumulative-baseline checks; no device or compiler."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import build_extreme_overlay as build


class OverlayTests(unittest.TestCase):
    def test_cumulative_failsafe_and_telemetry(self):
        payload = build.source_payload()
        baseline = build.read_baseline()
        for name in ('crossmix/session_metrics.py', 'crossmix/session_report.py', 'failsafe_state.py'):
            path = build.PREFIX + name
            self.assertIn(path, payload)
            self.assertNotEqual(build.sha(payload[path]), baseline[path])
        self.assertIn(b'world_loaded_seen', payload[build.PREFIX + 'crossmix/session_report.py'])
        self.assertIn(b'session_reached_world', payload[build.PREFIX + 'failsafe_state.py'])
        self.assertIn(b'top_threads_by_cpu_one_core', payload[build.PREFIX + 'crossmix/session_metrics.py'])
        # The saved original/newer user's config must never be part of the ZIP.
        self.assertNotIn(build.PREFIX + 'config/performance-018.json', payload)
        self.assertEqual(json.loads(payload[build.PREFIX + 'crossmix/performance-018.default.json'])['texture_dequeue'], 4)
        self.assertIn(b'MCPE_PERF_PROFILE', payload[build.PREFIX + 'crossmix/upstream-entry.sh'])
        self.assertIn(b'performance_fps_cap', payload[build.PREFIX + 'menu/main.lua'])
        self.assertIn(b'cleanup_menu.py', payload[build.PREFIX + 'crossmix/entry.sh'])
        self.assertIn('Roms/PORTS/Minecraft Bedrock Launcher.sh', payload)
        cover = payload['Imgs/PORTS/Minecraft Bedrock Launcher.png']
        self.assertEqual(cover[:24], b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x04\x00\x00\x00\x06\x00')

    def test_archive_manifest_modes_and_no_overwrite(self):
        payload = build.source_payload()
        manifest = build.manifest_for(payload, build.read_baseline(), 'fixture')
        payload[build.MANIFEST] = (json.dumps(manifest) + '\n').encode()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'overlay.zip'
            digest = build.write_archive(path, payload)
            self.assertEqual(digest, build.sha(path.read_bytes()))
            with zipfile.ZipFile(path) as archive:
                recorded = json.loads(archive.read(build.MANIFEST))
                for name, expected in recorded['files'].items():
                    self.assertEqual(expected, build.sha(archive.read(name)))
                info = archive.getinfo(build.PREFIX + 'crossmix/session.sh')
                self.assertTrue(info.external_attr >> 16 & 0o111)
            with self.assertRaises(AssertionError):
                build.write_archive(path, payload)

    def test_reject_proprietary_or_user_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ('config/settings.cfg', 'profiles/world/level.dat', 'versions/game/libminecraftpe.so', 'apk/game.apk', '../other-port/file'):
                with self.subTest(name=name), self.assertRaises(AssertionError):
                    build.write_archive(Path(temp) / 'rejected.zip', {build.PREFIX + name: b'x'})


if __name__ == '__main__':
    unittest.main()
