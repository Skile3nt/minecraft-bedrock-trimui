#!/usr/bin/env python3
"""Host-only A/B orchestration and stale-report regression; no ARM/GPU execution."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

C=Path(__file__).resolve().parent


def main():
    for auto,explicit in ((1,0),(0,0),(47,23)):
        with tempfile.TemporaryDirectory(prefix='mcpe SDL session ') as temp:
            g=Path(temp)/'game';a=g/'crossmix';(a/'bin').mkdir(parents=True);(g/'logs').mkdir()
            for n in ('sdl-test.sh','sdl_test_report.py'):shutil.copyfile(C/n,a/n)
            shim=a/'bin/bash';shim.write_text('#!/bin/sh\nexec bash "$@"\n');shim.chmod(0o755)
            (a/'session.sh').write_text('''#!/bin/bash
set -eu
[ "$MCPE_GRAPHICS_PROBE" = 1 ] && [ "$1" = 20 ]
v=auto; [ "${MCPE_SDL_PROBE_EXPLICIT_EGL:-0}" != 1 ] || v=explicit
python3 - "$GAMEDIR" "$v" <<'PY'
import json,sys,os
from pathlib import Path
g=Path(sys.argv[1]);v=sys.argv[2]
assert json.loads((g/'logs/crossmix-session-report.json').read_text())=={},'stale report reused'
code=int(os.environ['FIXTURE_'+v.upper()])
(g/'logs/crossmix-session-report.json').write_text(json.dumps({'variant':v,'exit_code':code}))
for n in ('crossmix-session.log','crossmix-client.log','crossmix-weston.log'):(g/'logs'/n).write_text(v)
sys.exit(code)
PY
''')
            (g/'logs/crossmix-session-report.json').write_text('{"old_attempt":true}')
            p=subprocess.run(['bash',str(a/'sdl-test.sh')],env=dict(os.environ,GAMEDIR=str(g),
                FIXTURE_AUTO=str(auto),FIXTURE_EXPLICIT=str(explicit)),text=True,capture_output=True,timeout=10)
            assert p.returncode==int(bool(auto or explicit)),(p.returncode,p.stdout,p.stderr)
            report=json.loads((g/'logs/crossmix-sdl-test.json').read_text())
            assert report['minecraft_started'] is False
            assert report['variants']['auto']['exit_code']==auto
            assert report['variants']['explicit']['exit_code']==explicit
            logs=Path(report['logs_directory'])
            assert json.loads((logs/'prior/crossmix-session-report.json').read_text())=={'old_attempt':True}
            for v in ('auto','explicit'):
                assert report['variants'][v]['session_report']['variant']==v
                assert (logs/v/'crossmix-client.log').read_text()==v
    print('PASS SDL A/B session: two failures, mixed result, success; no stale report; prior logs preserved; no Minecraft execution')


if __name__=='__main__':main()
