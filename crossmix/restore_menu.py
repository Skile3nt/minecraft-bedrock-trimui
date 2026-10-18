#!/usr/bin/env python3
"""Restore the final migration's saved PortMaster shortcuts without user data."""
import hashlib
import json
from pathlib import Path
import sys


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: restore_menu.py PORTS_DIR GAME_DIR')
    ports, game = (Path(value).resolve() for value in sys.argv[1:])
    state_path = game/'config/final-menu-cleanup.json'
    state = json.loads(state_path.read_text())
    backup = game/'backups/final-menu-cleanup'
    restored = []
    for item in state.get('moved', []):
        name, expected = item['name'], item['sha256']
        source, target = backup/name, ports/name
        if not source.is_file() or source.is_symlink() or digest(source) != expected:
            raise SystemExit(f'backup changed or missing: {name}')
        if target.exists():
            if not target.is_file() or target.is_symlink() or digest(target) != expected:
                raise SystemExit(f'refuse to replace current shortcut: {name}')
            source.unlink()
        else:
            source.replace(target)
        restored.append(name)
    (backup/'RESTORED.json').write_text(json.dumps({'restored': restored}, indent=2) + '\n')


if __name__ == '__main__':
    main()
