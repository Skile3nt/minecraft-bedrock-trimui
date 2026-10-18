#!/usr/bin/env python3
"""Move only this port's legacy menu shortcuts out of CrossMix's game list.

The final entry invokes this once.  Moves are on the same FAT volume and the
original files are retained under the port backup directory for rollback.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

LEGACY = (
    'Minecraft Bedrock CrossMix.sh',
    'Minecraft Bedrock Diagnostics.sh',
    'Minecraft Bedrock GPU Test.sh',
    'Minecraft Bedrock SDL Test.sh',
    'Minecraft Bedrock Input Test.sh',
    'Minecraft Bedrock Original.sh',
    'Minecraft Bedrock No Particles.sh',
    'Minecraft Bedrock Performance.sh',
    'Minecraft Bedrock No Particles Assets.sh',
)
FINAL = 'Minecraft Bedrock Launcher.sh'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: cleanup_menu.py PORTS_ENTRY_DIR GAME_DIR')
    ports = Path(sys.argv[1]).resolve()
    game = Path(sys.argv[2]).resolve()
    if ports.name != 'PORTS' or not game.is_dir():
        raise SystemExit('unexpected CrossMix paths')
    final = ports / FINAL
    if not final.is_file() or final.is_symlink():
        raise SystemExit('final launcher entry is missing')
    root = ports.parent.parent.resolve()
    if not ports.is_relative_to(root) or not game.is_relative_to(root):
        raise SystemExit('refuse paths outside the card')
    state = game / 'config' / 'final-menu-cleanup.json'
    if state.exists():
        return
    backup = game / 'backups' / 'final-menu-cleanup'
    backup.mkdir(mode=0o700, parents=True, exist_ok=True)
    state.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    moved = []
    for name in LEGACY:
        source = ports / name
        if not source.exists():
            continue
        # The names were generated exclusively by prior versions of this port.
        # Still refuse directories/symlinks and retain an exact hash for undo.
        if not source.is_file() or source.is_symlink():
            raise SystemExit(f'refuse unexpected legacy entry: {name}')
        target = backup / name
        if target.exists():
            if not target.is_file() or digest(target) != digest(source):
                raise SystemExit(f'backup conflict: {name}')
            source.unlink()
        else:
            os.replace(source, target)
        moved.append({'name': name, 'sha256': digest(target)})
    temporary = state.with_suffix('.tmp')
    temporary.write_text(json.dumps({'version': 1, 'final_entry': FINAL, 'moved': moved}, indent=2) + '\n')
    with temporary.open('rb') as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, state)
    directory = os.open(state.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


if __name__ == '__main__':
    main()
