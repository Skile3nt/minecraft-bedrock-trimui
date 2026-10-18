#!/usr/bin/env python3
"""Keep A/B evidence separate; never promote a diagnostic variant to a fix."""
import datetime
import json
from pathlib import Path
import sys


def summarize(root):
    result = {'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'test': 'pinned Crusty SDL backend; auto vs explicit native EGL loading',
              'logs_directory': str(root), 'minecraft_started': False,
              'note': 'Diagnostic only. Explicit loading is not enabled for Minecraft.', 'variants': {}}
    for variant in ('auto', 'explicit'):
        p = root/variant
        code = int((p/'exit-code.txt').read_text())
        report = p/'crossmix-session-report.json'
        result['variants'][variant] = {'exit_code': code,
            'session_report': json.loads(report.read_text()) if report.exists() else None}
    return result


if __name__ == '__main__':
    data = summarize(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(data, indent=2)+'\n')
    print('sdl_test_result='+json.dumps({k:v['exit_code'] for k,v in data['variants'].items()}))
