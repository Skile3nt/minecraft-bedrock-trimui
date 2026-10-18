#!/usr/bin/env python3
"""Final menu migration: only known entries move, and no card is touched."""
import json
from pathlib import Path
import tempfile
import unittest

import cleanup_menu as cleanup
import restore_menu


class MenuCleanupTests(unittest.TestCase):
    def build(self, root):
        ports = root/'Roms/PORTS'; game = root/'Data/ports/minecraftbedrock'
        ports.mkdir(parents=True); game.mkdir(parents=True)
        (ports/cleanup.FINAL).write_text('#!/bin/sh\n')
        for name in cleanup.LEGACY:
            (ports/name).write_text('#!/bin/sh\nentry_mode=legacy\n')
        (ports/'Unrelated Port.sh').write_text('#!/bin/sh\n')
        return ports, game

    def test_moves_only_known_shortcuts_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            ports, game = self.build(Path(temp))
            cleanup.main = cleanup.main
            import sys
            old = sys.argv; sys.argv = ['cleanup_menu.py', str(ports), str(game)]
            try: cleanup.main(); cleanup.main()
            finally: sys.argv = old
            backup = game/'backups/final-menu-cleanup'
            self.assertTrue((ports/cleanup.FINAL).exists())
            self.assertTrue((ports/'Unrelated Port.sh').exists())
            for name in cleanup.LEGACY:
                self.assertFalse((ports/name).exists())
                self.assertTrue((backup/name).is_file())
            state = json.loads((game/'config/final-menu-cleanup.json').read_text())
            self.assertEqual(len(state['moved']), len(cleanup.LEGACY))
            old = sys.argv; sys.argv = ['restore_menu.py', str(ports), str(game)]
            try: restore_menu.main()
            finally: sys.argv = old
            for name in cleanup.LEGACY:
                self.assertTrue((ports/name).is_file())
                self.assertFalse((backup/name).exists())

    def test_refuses_symlink_without_moving_anything(self):
        with tempfile.TemporaryDirectory() as temp:
            ports, game = self.build(Path(temp))
            bad = ports/cleanup.LEGACY[0]
            bad.unlink(); bad.symlink_to(ports/'Unrelated Port.sh')
            import sys
            old = sys.argv; sys.argv = ['cleanup_menu.py', str(ports), str(game)]
            try:
                with self.assertRaises(SystemExit): cleanup.main()
            finally: sys.argv = old
            self.assertTrue((ports/cleanup.LEGACY[1]).exists())
            self.assertFalse((game/'config/final-menu-cleanup.json').exists())


if __name__ == '__main__':
    unittest.main()
