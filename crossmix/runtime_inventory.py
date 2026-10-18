#!/usr/bin/env python3
"""Hash only selected runtime files; no environment dump or account data."""
import hashlib
import json
import os
from pathlib import Path
import sys


def inventory():
    result = {}
    for key in ('CRUSTY_LIBSDL', 'CRUSTY_LIBEGL', 'CRUSTY_LIBGLES'):
        value = os.environ.get(key)
        item = {'configured_path': value}
        try:
            if not value: raise ValueError('library path unset')
            p = Path(value)
            with p.open('rb') as f:
                header = f.read(20); f.seek(0)
                digest = hashlib.file_digest(f, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else None
            item.update(resolved_path=str(p.resolve()), size=p.stat().st_size,
                        sha256=digest, elf_class=header[4] if len(header)>4 else None,
                        elf_machine=int.from_bytes(header[18:20], 'little'),
                        arm64=header[:5]==b'\x7fELF\x02' and header[18:20]==b'\xb7\x00')
        except (OSError, ValueError) as e: item['inspection_error'] = str(e)
        result[key] = item
    return {'libraries': result,
            'note': 'Configured native objects; actual SDL/EGL bindings are in crossmix-client.log. No GPU validation.'}


if __name__ == '__main__':
    data = json.dumps(inventory(), indent=2)+'\n'
    Path(sys.argv[1]).write_text(data)
    print('runtime_inventory='+data.strip())
