#!/usr/bin/env python3
"""Exercise the real update and rollback in an isolated card-shaped directory."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import tempfile
import unittest
import zipfile
import build_launcher_polish as build
import apply_launcher_polish as install

class Tests(unittest.TestCase):
    def test_install_rollback_and_protected_save(self):
        with tempfile.TemporaryDirectory() as folder:
            card=Path(folder);install.previous.CARD=card
            with zipfile.ZipFile(build.ORIGINAL) as z:
                before={n:z.read(n) for n in z.namelist()}
                for n,b in before.items():
                    p=card/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
            world=card/'Data/ports/minecraftbedrock/profiles/world/level.dat'
            world.parent.mkdir(parents=True);world.write_bytes(b'world-sentinel')
            data=build.payload();backup=card/'Data/ports/minecraftbedrock/backups/test'
            self.assertGreater(install.apply(data,backup),0)
            for n,b in data.items():self.assertEqual((card/n).read_bytes(),b)
            self.assertEqual(world.read_bytes(),b'world-sentinel')
            changed=card/'Data/ports/minecraftbedrock/menu/main.lua'
            changed.write_bytes(b'user-modification')
            with self.assertRaises(AssertionError):install.rollback(backup)
            self.assertEqual(changed.read_bytes(),b'user-modification')
            changed.write_bytes(data['Data/ports/minecraftbedrock/menu/main.lua'])
            install.rollback(backup)
            for n,b in before.items():self.assertEqual((card/n).read_bytes(),b)
            for n in set(data)-set(before):self.assertFalse((card/n).exists())
            self.assertEqual(world.read_bytes(),b'world-sentinel')

if __name__=='__main__':unittest.main()
