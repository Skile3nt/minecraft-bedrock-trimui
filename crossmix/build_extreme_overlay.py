#!/usr/bin/env python3
"""Build the cumulative final-candidate overlay over a clean 0.1.9 install."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
PREFIX = 'Data/ports/minecraftbedrock/'
VERSION = '1.0.0-rc1'
BASE = DIST / 'minecraft-bedrock-crossmix-0.1.9-experimental.zip'
BASE_SHA256 = 'c0971bd79548737a9009dc693da2137ce58d4b44997b87f4c89028c4b2c058d9'
OUTPUT = DIST / 'Minecraft-Bedrock-TrimUI-1.0.0-rc1-Final-Candidate-r3.zip'
MANIFEST = PREFIX + 'crossmix/FINAL_CANDIDATE_MANIFEST.json'
BINARY_SOURCES = ('isolate-crusty', 'particle-audit', 'sdl-trace')
# Unlike 0.2.2-r2, include the complete post-0.1.9 failsafe and telemetry pair.
# The default template is code; config/performance-018.json is user state.
SOURCE_MAP = {PREFIX + 'crossmix/' + name: 'crossmix/' + name for name in (
    'ADAPTATION_VERSION', 'session.sh', 'session_metrics.py', 'session_report.py',
    'performance_profiles.py', 'performance-018.default.json', 'HOTFIX_0.2.3.md',
    'cleanup_menu.py', 'restore_menu.py', 'entry.sh',
    'isolate-crusty.c', 'particle-audit.c', 'sdl-trace.c',
)}
SOURCE_MAP.update({
    PREFIX + 'crossmix/upstream-entry.sh': 'portmaster/minecraftbedrock/Minecraft Bedrock.sh',
    PREFIX + 'menu/main.lua': 'portmaster/minecraftbedrock/minecraftbedrock/menu/main.lua',
    PREFIX + 'failsafe_state.py': 'portmaster/minecraftbedrock/minecraftbedrock/failsafe_state.py',
    PREFIX + 'crossmix/source/final-candidate/LICENSE': 'LICENSE',
    PREFIX + 'crossmix/source/final-candidate/build_final_overlay.py': 'crossmix/build_extreme_overlay.py',
    'Imgs/PORTS/Minecraft Bedrock Launcher.png': 'crossmix/assets/minecraft_bedrock_launcher_cover.png',
})
# Baseline fingerprints for the later installer, not files to overwrite.
PRESERVED_DEPENDENCIES = tuple(PREFIX + name for name in (
    'bin/mcpelauncher-client', 'crossmix/input-bridge.so', 'crossmix/egl-bind-audit.so',
    'crossmix/sdl-session-probe', 'crossmix/entry.sh', 'run_bedrock.sh',
    'lib/failsafe.sh', 'controls/trimui.gamecontrollerdb.txt',
))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_payload():
    payload = {name: (ROOT / source).read_bytes() for name, source in SOURCE_MAP.items()}
    entry = payload[PREFIX + 'crossmix/entry.sh']
    marker = b'entry_mode=${1:-}'
    assert entry.count(marker) == 1
    payload['Roms/PORTS/Minecraft Bedrock Launcher.sh'] = entry.replace(marker, b'entry_mode=--finalize')
    return payload


def read_baseline():
    with BASE.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == BASE_SHA256, '0.1.9 baseline hash mismatch'
    with zipfile.ZipFile(BASE) as archive:
        manifest = json.loads(archive.read(PREFIX + 'crossmix/MANIFEST.json'))
        assert manifest['adaptation'] == '0.1.9-experimental'
        for name in PRESERVED_DEPENDENCIES:
            assert sha(archive.read(name)) == manifest['files'][name], name
    return manifest['files']


def assert_arm64_library(data):
    # ELF64, little-endian, ET_DYN, EM_AARCH64. ABI/dependencies are also
    # checked with readelf during the actual build, without executing ARM code.
    assert data[:6] == b'\x7fELF\x02\x01'
    assert int.from_bytes(data[16:18], 'little') == 3
    assert int.from_bytes(data[18:20], 'little') == 183


def compile_libraries(payload, directory):
    flags = ['-O2', '-Wall', '-Wextra', '-Werror', '-fPIC', '-shared']
    for stem in BINARY_SOURCES:
        output = directory / (stem + '.so')
        subprocess.run(['aarch64-linux-gnu-gcc', *flags,
                        str(ROOT / 'crossmix' / (stem + '.c')),
                        '-ldl', '-o', str(output)], check=True)
        data = output.read_bytes()
        assert_arm64_library(data)
        subprocess.run(['aarch64-linux-gnu-readelf', '-d', str(output)],
                       check=True, stdout=subprocess.DEVNULL)
        payload[PREFIX + 'crossmix/' + stem + '.so'] = data


def manifest_for(payload, baseline, commit):
    return {
        'version': VERSION, 'cumulative_from': '0.1.9-experimental',
        'baseline_zip_sha256': BASE_SHA256, 'source_commit': commit,
        'hardware_tested': False,
        'files': {name: sha(data) for name, data in sorted(payload.items())},
        'baseline_files': {name: baseline.get(name) for name in sorted(payload)},
        'preserved_dependencies': {name: baseline[name] for name in PRESERVED_DEPENDENCIES},
        'cumulative_fixes': ['8cc07fe failsafe/report world-marker pair',
                            '82d63dd launcher profile handoff', '244e657 thread telemetry',
                            '44c52af tmpfs trace', '5b68cd9 monotonic cadence',
                            '0.2.2-r2 capped trace and failsafe-safe 30/40/50 experiment',
                            'final single PortMaster entry and reversible legacy shortcut cleanup'],
        'configuration_policy': 'Never overwrite live config. Preserve existing texture_dequeue. '
                                'For a pristine 0.1.9 null/missing value, a separately backed-up '
                                'key-only migration to 4 is required to reproduce the later Performance setup.',
        'installation_gate': 'Uninstalled; require positively identified card and clean read-only FAT check.',
        'menu_cleanup': {'final_entry': 'Roms/PORTS/Minecraft Bedrock Launcher.sh',
                         'cover': 'Imgs/PORTS/Minecraft Bedrock Launcher.png',
                         'legacy_entries_moved_to': 'Data/ports/minecraftbedrock/backups/final-menu-cleanup/'},
        'rollback': 'Back up all differing destination files before first replacement. Record new paths. '
                    'Restore only if their current hashes still match this manifest; never restore user data.',
    }


def write_archive(output, payload):
    assert not output.exists() and not output.with_suffix(output.suffix + '.sha256').exists(), 'Preserve existing artifact'
    for name in payload:
        assert '..' not in Path(name).parts
        if name.startswith(PREFIX):
            rel = name.removeprefix(PREFIX)
            assert not rel.startswith(('config/', 'profiles/', 'versions/', 'apk/', 'logs/', 'backups/', 'controls/'))
        else:
            assert name in ('Roms/PORTS/Minecraft Bedrock Launcher.sh',
                            'Imgs/PORTS/Minecraft Bedrock Launcher.png')
        assert not name.endswith(('.apk', '.apks', '.mcworld', '/libminecraftpe.so'))
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 15, 0, 0, 0))
            info.external_attr = (0o100755 if name.endswith(('.sh', '.so')) else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(payload)
        for name, data in payload.items():
            assert sha(archive.read(name)) == sha(data), name
    digest = sha(output.read_bytes())
    output.with_suffix(output.suffix + '.sha256').write_text(f'{digest}  {output.name}\n')
    return digest


def main():
    assert (ROOT / 'crossmix/ADAPTATION_VERSION').read_text().strip() == VERSION
    baseline = read_baseline()
    payload = source_payload()
    with tempfile.TemporaryDirectory(prefix='mcpe-023-build-', dir=DIST) as temp:
        compile_libraries(payload, Path(temp))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    payload[MANIFEST] = (json.dumps(manifest_for(payload, baseline, commit), indent=2) + '\n').encode()
    print(OUTPUT, 'sha256=' + write_archive(OUTPUT, payload), 'files=' + str(len(payload)))


if __name__ == '__main__':
    main()
