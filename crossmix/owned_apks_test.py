#!/usr/bin/env python3
"""Host safety regressions; no actual Google credentials or Minecraft files."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import install_owned_apks as installer


class VerificationTests(unittest.TestCase):
    def test_copy_error_stops_peer_workers_immediately(self):
        guard = installer.UsbGuard.__new__(installer.UsbGuard)
        guard.aborted = threading.Event()
        with patch.object(guard, "_copy_checked", side_effect=OSError("synthetic read failure")):
            with self.assertRaises(OSError):
                guard.copy(Path("source"), Path("target"))
        self.assertTrue(guard.aborted.is_set())

    def test_another_play_version_code_is_never_substituted(self):
        sys.path.insert(0, str(installer.ROOT / "tests"))
        from test_apkmeta import apk
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "wrong-build.apk"
            apk(path, installer.VERSION, 951622101, "full")
            with patch.object(installer, "verify_signature"):
                with self.assertRaisesRegex(RuntimeError, "version mismatch"):
                    installer.verify_set([path], Path("apksigner"))

    def test_failing_verifier_cannot_pass_using_a_printed_mojang_certificate(self):
        cert = next(iter(installer.apkmeta.MOJANG_CERTS))
        output = f"Signer #1 certificate SHA-256 digest: {cert}"
        with patch.object(installer.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, output, "failed")):
            with self.assertRaisesRegex(RuntimeError, "cryptographic"):
                installer.verify_signature(Path("test.apk"), Path("apksigner"))

    def test_valid_signature_with_wrong_identity_is_rejected(self):
        output = "Signer #1 certificate SHA-256 digest: " + "a" * 64
        with patch.object(installer.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            with self.assertRaisesRegex(RuntimeError, "cryptographic"):
                installer.verify_signature(Path("test.apk"), Path("apksigner"))

    def test_google_source_stamp_is_separate_from_mojang_apk_signature(self):
        cert = next(iter(installer.apkmeta.MOJANG_CERTS))
        output = (f"Signer #1 certificate SHA-256 digest: {cert}\n"
                  "Source Stamp Signer certificate SHA-256 digest: " + "b" * 64 + "\n")
        with patch.object(installer.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            installer.verify_signature(Path("test.apk"), Path("apksigner"))

    def test_internal_disk_never_passes_trimui_identity(self):
        disks = {"blockdevices": [{"path": "/dev/nvme0n1", "tran": "nvme", "serial": installer.SERIAL, "model": "TRIMUI ADB"}]}
        with patch.object(installer, "run", return_value=json.dumps(disks)):
            with self.assertRaisesRegex(RuntimeError, "USB identity"):
                installer.card_identity(Path("/"))

    def test_missing_usb_uuid_never_passes(self):
        disks = {"blockdevices": [{"path": "/dev/sda", "tran": "usb", "serial": installer.SERIAL, "model": "TRIMUI ADB", "children": [{"uuid": "OTHER", "mountpoints": ["/card"]}]}]}
        with patch.object(installer, "run", return_value=json.dumps(disks)):
            with self.assertRaisesRegex(RuntimeError, "UUID"):
                installer.card_identity(Path("/card"))

    def test_arm32_and_x86_cannot_pass_as_arm64_game(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "library.so"
            for elf_class, machine in [(1, 40), (2, 62), (2, 183)]:
                data = bytearray(20)
                data[:6] = b"\x7fELF" + bytes([elf_class, 1])
                struct.pack_into("<H", data, 18, machine)
                path.write_bytes(data)
                if machine == 183:
                    installer.verify_elf(path)
                else:
                    with self.assertRaisesRegex(RuntimeError, "AArch64"):
                        installer.verify_elf(path)

    def test_selecting_build_preserves_controller_and_performance_settings(self):
        before = b"controller=Xbox\r\nfps_cap=30\nversion=older\nrender_distance=4"
        after = installer.selected_settings(before)
        self.assertEqual(after, b"controller=Xbox\r\nfps_cap=30\nrender_distance=4\nversion=1.16.221.01-971622101-arm64\n")

    def publication_fixture(self, root):
        card = root / "card"
        game = card / "Data/ports/minecraftbedrock"
        for name in ("crossmix", "config", "logs", "versions"):
            (game / name).mkdir(parents=True)
        (game / "crossmix/ADAPTATION_VERSION").write_text("0.1.2-experimental")
        (game / "config/settings.cfg").write_bytes(b"controller=Xbox\nfps_cap=30\n")
        (game / "logs/launcher.log").write_text("previous evidence")
        (card / "other-game.txt").write_text("preserve me")
        prepared = root / "prepared"
        (prepared / "lib/arm64-v8a").mkdir(parents=True)
        (prepared / "lib/arm64-v8a/libminecraftpe.so").write_bytes(b"synthetic library")
        (prepared / "version.json").write_text(json.dumps({"package": installer.apkmeta.PACKAGE,
            "version_name": installer.VERSION, "version_code": installer.CODE,
            "abi_label": "arm64", "game_library_sha256": "fixture", "compatibility": {}}))
        evidence = root / "evidence"
        evidence.mkdir()
        return card, game, prepared, evidence

    def test_publication_backs_up_settings_and_preserves_other_games(self):
        class Guard:
            errors = []
            def __init__(self, card): pass
            def check(self): pass
            def close(self): pass
            def stop(self): pass
            def copy(self, source, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        with tempfile.TemporaryDirectory() as temporary:
            card, game, prepared, evidence = self.publication_fixture(Path(temporary))
            original_run = installer.subprocess.run
            def controlled_run(argv, **kwargs):
                if argv[0] == "sync":
                    return subprocess.CompletedProcess(argv, 0)
                return original_run(argv, **kwargs)
            with patch.object(installer, "card_identity", return_value={"fixture": True}), \
                 patch.object(installer, "UsbGuard", Guard), \
                 patch.object(installer.subprocess, "run", side_effect=controlled_run):
                result = installer.publish(prepared, card, evidence, "test")
            self.assertEqual(result["selected"], installer.TARGET)
            self.assertEqual((game / "backups/owned-apk-test/settings.cfg").read_bytes(), b"controller=Xbox\nfps_cap=30\n")
            self.assertEqual((game / "backups/owned-apk-test/logs/launcher.log").read_text(), "previous evidence")
            self.assertEqual((card / "other-game.txt").read_text(), "preserve me")
            self.assertIn(installer.TARGET.encode(), (game / "config/settings.cfg").read_bytes())

    def test_interrupted_copy_does_not_publish_or_change_selected_version(self):
        class Guard:
            errors = []
            def __init__(self, card): pass
            def check(self): pass
            def close(self): pass
            def stop(self): pass
            def copy(self, source, target):
                if source.name == "libminecraftpe.so":
                    raise OSError("simulated USB failure")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        with tempfile.TemporaryDirectory() as temporary:
            card, game, prepared, evidence = self.publication_fixture(Path(temporary))
            with patch.object(installer, "card_identity", return_value={"fixture": True}), \
                 patch.object(installer, "UsbGuard", Guard):
                with self.assertRaisesRegex(OSError, "USB failure"):
                    installer.publish(prepared, card, evidence, "test")
            self.assertFalse((game / "versions" / installer.TARGET).exists())
            self.assertEqual((game / "config/settings.cfg").read_bytes(), b"controller=Xbox\nfps_cap=30\n")
            self.assertEqual((card / "other-game.txt").read_text(), "preserve me")


if __name__ == "__main__":
    unittest.main()
