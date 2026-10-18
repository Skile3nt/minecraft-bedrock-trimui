#!/usr/bin/env python3
"""Host installer for the exact, legally obtained TrimUI reference build.

No account access or download logic. Uses the upstream transactional installer
locally before any SD write. Default is preparation only; --install publishes
the prepared version on the identified CrossMix card and remembers it.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "portmaster/minecraftbedrock/minecraftbedrock"
sys.path.insert(0, str(RUNTIME))
import apkmeta

VERSION = "1.16.221.01"
CODE = 971622101
TARGET = f"{VERSION}-{CODE}-arm64"
SERIAL = "1c000c660500c8d251d"
UUID = "1B16-2B5A"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(argv: list[str]) -> str:
    return subprocess.check_output(argv, text=True, timeout=30)


def card_identity(card: Path) -> dict:
    disks = json.loads(run(["lsblk", "--tree", "-J", "-o", "PATH,TRAN,MODEL,SERIAL,UUID,MOUNTPOINTS"]))["blockdevices"]
    devices = [d for d in disks if d.get("tran") == "usb"
               and d.get("serial") == SERIAL and d.get("model", "").strip() == "TRIMUI ADB"]
    if len(devices) != 1:
        raise RuntimeError("TrimUI USB identity is not unique")
    parts = [p for p in devices[0].get("children", []) if p.get("uuid") == UUID]
    if len(parts) != 1 or str(card) not in (parts[0].get("mountpoints") or []):
        raise RuntimeError("Expected SD UUID or mount point changed")
    mount = json.loads(run(["findmnt", "-J", "-T", str(card), "-o", "SOURCE,TARGET,FSTYPE,OPTIONS"]))["filesystems"][0]
    if (mount["source"] != parts[0]["path"] or mount["target"] != str(card)
            or mount["fstype"] != "vfat" or "rw" not in mount["options"].split(",")):
        raise RuntimeError("Unexpected or read-only SD filesystem")
    for name in ("Roms", "Data", "System", "Apps/PortMaster", "Emus/PORTS"):
        if not (card / name).is_dir():
            raise RuntimeError(f"CrossMix structure missing: {name}")
    if (card / "System/usr/trimui/crossmix-version.txt").read_text().strip() != "1.3.0":
        raise RuntimeError("Unexpected CrossMix version")
    return mount


def verify_signature(path: Path, signer: Path) -> None:
    result = subprocess.run([str(signer), "verify", "--print-certs", str(path)],
                            capture_output=True, text=True, timeout=120)
    # A certificate printed by a failing verifier is never sufficient.
    # Google's Source Stamp is a distributor attestation, not an APK signer.
    certs = re.findall(r"^Signer #\d+ certificate SHA-256 digest:\s*([0-9a-f:]+)",
                       result.stdout, re.I | re.M)
    certs = {c.replace(":", "").lower() for c in certs}
    if result.returncode != 0 or len(certs) != 1 or not certs.issubset(apkmeta.MOJANG_CERTS):
        raise RuntimeError(f"APK cryptographic verification failed: {path.name}")


def verify_set(paths: list[Path], signer: Path) -> list:
    if not paths or any(p.suffix.lower() != ".apk" or not p.is_file() for p in paths):
        raise RuntimeError("Supply the original APKs from one complete download")
    infos = []
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"APK CRC failure: {path.name}")
        verify_signature(path, signer)
        infos.append(apkmeta.inspect_apk(path, path.name, path.name))
    if apkmeta.normalized_group(infos) != (apkmeta.PACKAGE, CODE, VERSION):
        raise RuntimeError("Package/version mismatch; no substitute build is accepted")
    apkmeta.validate_signers(infos)
    natives, _, _ = apkmeta.choose_sources(infos)
    if set(natives) != {"arm64-v8a"}:
        raise RuntimeError("This install requires exclusively arm64-v8a game libraries")
    return infos


def verify_elf(path: Path) -> None:
    with path.open("rb") as stream:
        header = stream.read(20)
    if len(header) < 20 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", header, 18)[0] != 183:
        raise RuntimeError(f"Not an AArch64 ELF: {path.name}")


def selected_settings(previous: bytes) -> bytes:
    # Keep other settings and controller choices byte-for-byte.
    lines = previous.splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith(b"version=")]
    data = b"".join(kept)
    if data and not data.endswith(b"\n"):
        data += b"\n"
    return data + f"version={TARGET}\n".encode()


class UsbGuard:
    def __init__(self, card: Path):
        self.card = card
        self.errors = []
        self.aborted = threading.Event()
        self.process = subprocess.Popen(
            ["journalctl", "-k", "-f", "--since", "now", "-o", "cat", "--no-pager"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.thread = threading.Thread(target=self.watch, daemon=True)
        self.thread.start()

    def watch(self):
        failure = re.compile(r"I/O error|Buffer I/O|critical.*error|USB disconnect|reset .*USB device|error -\d+|FAT-fs.*(?:error|corrupt|invalid|failed)", re.I)
        for line in self.process.stdout:
            if ("sda" in line or re.search(r"usb \d+-", line)) and failure.search(line):
                self.errors.append(line.strip())

    def check(self):
        if self.aborted.is_set() or self.errors or self.process.poll() is not None or not self.card.is_mount():
            raise OSError("USB monitoring/connection failed; stop writes")

    def stop(self):
        self.aborted.set()

    def copy(self, source: Path, target: Path):
        try:
            self._copy_checked(source, target)
        except BaseException:
            # Stop peer workers immediately, regardless of ordered future reads.
            self.stop()
            raise

    def _copy_checked(self, source: Path, target: Path):
        self.check()
        if source.is_symlink() or target.exists():
            raise RuntimeError("Refusing symlink or unbacked replacement")
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as inp, target.open("xb") as out:
            while chunk := inp.read(1024 * 1024):
                self.check()
                out.write(chunk)
            out.flush()
        self.check()
        if sha(source) != sha(target):
            raise OSError("Transfer checksum mismatch; stop writes")

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=5)


def copy_assets(guard, files, prepared, staging):
    # The FAT 'flush' mount option sleeps ~100ms on each writable close.
    # Bounded independent copies overlap that wait without remounting the SD.
    pool = ThreadPoolExecutor(max_workers=8)
    try:
        for count, _ in enumerate(pool.map(
                lambda source: guard.copy(source, staging / source.relative_to(prepared)), files), 1):
            if count % 1000 == 0:
                print(f"copy_progress={count}/{len(files)}", flush=True)
    except BaseException:
        guard.stop()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def publish(prepared: Path, card: Path, evidence: Path, stamp: str) -> dict:
    mount = card_identity(card)
    game = card / "Data/ports/minecraftbedrock"
    if game.is_symlink() or not (game / "crossmix/ADAPTATION_VERSION").is_file():
        raise RuntimeError("Existing CrossMix port not found")
    for name in ("versions", "config", "backups"):
        if not (game / name).resolve().is_relative_to(game.resolve()):
            raise RuntimeError("Unsafe destination symlink")
    destination = game / "versions" / TARGET
    if destination.exists():
        raise RuntimeError("Reference version already exists; preserve and audit it before updating")
    files = [p for p in prepared.rglob("*") if p.is_file()]
    if shutil.disk_usage(game).free < sum(p.stat().st_size for p in files) + 64 * 1024 * 1024:
        raise RuntimeError("Insufficient SD space")
    settings = game / "config/settings.cfg"
    old = settings.read_bytes() if settings.exists() else b""
    updated = selected_settings(old)
    guard = UsbGuard(card)
    try:
        guard.check()
        backup = game / "backups" / ("owned-apk-" + stamp)
        backup.mkdir(parents=True, exist_ok=False)
        if settings.exists():
            guard.copy(settings, backup / "settings.cfg")
        for log in (game / "logs").glob("*"):
            if log.is_file():
                guard.copy(log, backup / "logs" / log.name)
        staging = destination.with_name(".owned-apk-" + stamp)
        staging.mkdir(parents=True, exist_ok=False)
        copy_assets(guard, files, prepared, staging)
        # FAT32 barriers per tiny asset are extremely costly. Flush the whole
        # staging tree and backups before making the version visible instead.
        subprocess.run(["sync", "-f", str(card)], check=True, timeout=120)
        guard.check()
        card_identity(card)
        guard.check()
        os.replace(staging, destination)
        local_settings = evidence / "selected-settings.cfg"
        local_settings.write_bytes(updated)
        temporary = settings.with_name(".owned-apk-settings-" + stamp)
        guard.copy(local_settings, temporary)
        guard.check()
        os.replace(temporary, settings)
        hashes = {str(p.relative_to(prepared)): sha(p) for p in files}
        for rel, digest in hashes.items():
            guard.check()
            if sha(destination / rel) != digest:
                raise OSError("Installed file checksum mismatch")
        if settings.read_bytes() != updated:
            raise OSError("Settings verification failed")
        selected = run([sys.executable, str(RUNTIME / "version_env.py"), str(game), "--select-latest"]).strip()
        if selected != TARGET:
            raise RuntimeError("Launcher did not recognize the reference version")
        subprocess.run(["sync", "-f", str(card)], check=True, timeout=120)
        guard.check()
        card_identity(card)
        return {"mount": mount, "version_directory": str(destination), "backup": str(backup),
                "verified_files": len(hashes), "sha256": hashes, "selected": selected,
                "sync": "passed", "kernel_errors": guard.errors,
                "permissions": "FAT has no persistent Unix mode; launcher reads game assets/libraries"}
    finally:
        guard.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apksigner", type=Path, required=True)
    parser.add_argument("--card", type=Path, default=Path("/run/media/skile/CROSSMIXOS"))
    parser.add_argument("--install", action="store_true")
    parser.add_argument("apks", type=Path, nargs="+")
    args = parser.parse_args()
    os.umask(0o077)
    if os.getenv("MCPE_ALLOW_UNVERIFIED_APK"):
        raise RuntimeError("Test-fixture bypass must be disabled")
    signer = args.apksigner.resolve()
    os.environ["PATH"] = str(signer.parent) + os.pathsep + os.environ["PATH"]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence = ROOT / "recovery/play-acquisition" / ("install-" + stamp)
    evidence.mkdir(parents=True, exist_ok=False)
    report = {"requested_version": VERSION, "requested_code": CODE, "status": "starting",
              "physical_game_tested": False}
    try:
        infos = verify_set([p.resolve() for p in args.apks], signer)
        report["original_apks"] = {str(p.resolve()): sha(p) for p in args.apks}
        report["signature"] = "apksigner verify succeeded; Mojang certificate allowlist matched"
        stage = evidence / "game"
        (stage / "compat").mkdir(parents=True)
        shutil.copy2(RUNTIME / "compat/compatibility.json", stage / "compat/compatibility.json")
        installed = apkmeta.install(stage, [p.resolve() for p in args.apks])
        if len(installed) != 1 or installed[0].name != TARGET:
            raise RuntimeError("Upstream installer produced an unexpected version")
        prepared = installed[0]
        for elf in (prepared / "lib/arm64-v8a").glob("*.so*"):
            verify_elf(elf)
        report["prepared_directory"] = str(prepared)
        report["status"] = "prepared"
        if args.install:
            report["installation"] = publish(prepared, args.card.resolve(), evidence, stamp)
            report["status"] = "installed_and_verified"
    except BaseException as error:
        report.update(status="stopped", error=str(error))
        raise
    finally:
        (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(evidence / "report.json"),
                      "installation": {k: v for k, v in report.get("installation", {}).items()
                                       if k != "sha256"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
