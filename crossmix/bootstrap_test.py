#!/usr/bin/env python3
"""Host-only failure injection for the POSIX bootstrap, never a GPU test."""
import os, shutil, subprocess, tempfile
from pathlib import Path
C = Path(__file__).resolve().parent


def script(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\n'+content+'\n')
    path.chmod(0o755)


def main():
    with tempfile.TemporaryDirectory(prefix='mcpe bootstrap ') as tmp:
        card = Path(tmp)
        ports = card/'Roms/PORTS'; ports.mkdir(parents=True)
        game = card/'Data/ports/minecraftbedrock'
        shutil.copytree(C, game/'crossmix', ignore=shutil.ignore_patterns('__pycache__'))
        entry = ports/'Minecraft Bedrock Diagnostics.sh'
        entry.write_text((C/'entry.sh').read_text().replace('entry_mode=${1:-}', 'entry_mode=--diagnose', 1))
        mock = card/'mocks'; mock.mkdir()
        script(mock/'uname', 'echo aarch64')
        script(game/'crossmix/status.sh', 'echo "status_message=$1"')
        script(game/'crossmix/bin/bash', 'echo bash_version=fixture; exit 0')
        env = dict(os.environ, PATH=str(mock)+':'+os.environ['PATH'])
        log = game/'logs/crossmix-entry.log'
        def invoke(expected, *args):
            log.unlink(missing_ok=True)
            r = subprocess.run(['sh', str(entry), *args], env=env, capture_output=True, text=True, timeout=5)
            assert r.returncode == expected, (r.returncode, r.stderr, log.read_text())
            text = log.read_text()
            assert '=== CrossMix bootstrap' in text and f'exit_code={expected}' in text, text
            return text
        # Fail before discovery, ensuring interpreter stderr and exit survive.
        python = card/'System/bin/python3.11'
        enc = card/'System/lib/python3.11/encodings/__init__.py'
        enc.parent.mkdir(parents=True); enc.touch()
        script(python, 'echo injected_python_failure >&2; exit 47')
        text = invoke(47)
        assert 'injected_python_failure' in text and 'stage=python' in text
        # A partial Python extraction produces a precise, logged error.
        enc.unlink()
        text = invoke(126)
        assert 'standard library missing' in text
        python.unlink()
        # Synthetic discovery does not load a real GPU or run ARM binaries.
        (game/'crossmix/probe.py').write_text('print("fixture_probe_no_gpu")\nraise SystemExit(23)\n')
        text = invoke(23)
        assert 'fixture_probe_no_gpu' in text and 'bash_status=0' in text
        assert 'stage=diagnostics-complete' in text and 'status_message=' in text
        (game/'crossmix/probe.py').write_text('print("fixture_probe_ok")\n')
        text = invoke(0)
        assert 'Diagnostics: checks OK' in text
        # Child errors must reach the top-level exit trap, instead of exec losing it.
        script(game/'crossmix/gpu-test.sh', 'echo fixture_graphics_no_render; exit 42')
        entry.write_text((C/'entry.sh').read_text().replace('entry_mode=${1:-}', 'entry_mode=--graphics-test', 1))
        text = invoke(42)
        assert 'stage=graphics-test' in text and 'fixture_graphics_no_render' in text
        # Missing shared entry cannot suppress logging: entries are self-contained.
        assert not (ports/'Minecraft Bedrock CrossMix.sh').exists()
        entry.write_text((C/'entry.sh').read_text())
        script(game/'crossmix/upstream-entry.sh', 'echo fixture_launcher; exit 29')
        script(game/'crossmix/bin/bash', '''if [ "$1" = -c ]; then echo bash_version=fixture; exit 0; fi
exec sh "$@"''')
        text = invoke(29)
        assert 'fixture_launcher' in text and 'stage=launcher' in text
        script(game/'crossmix/upstream-entry.sh', 'echo "SDL/EGL window failed" >"$GAMEDIR/logs/crossmix-failure.txt"; exit 1')
        text = invoke(1)
        assert 'status_message=Minecraft: SDL/EGL window failed (code 1)' in text
        script(game/'crossmix/upstream-entry.sh', 'exit 29')
        text = invoke(29)
        assert 'failed at launcher (code 29)' in text and 'SDL/EGL window failed' not in text
        # The private Bash wrapper scopes its new libc to Bash, preserving the
        # firmware library environment of commands launched by that shell.
        shutil.copyfile(C/'bin/bash', game/'crossmix/bin/bash')
        runtime = game/'crossmix/runtime/debian'
        script(runtime/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1', '''printf 'loader_args=%s\\n' "$*"
printf 'inherited_libraries=%s\\n' "$LD_LIBRARY_PATH"
exit 0''')
        r = subprocess.run(['sh', str(game/'crossmix/bin/bash'), '-c', 'true'],
                           env=dict(env, GAMEDIR=str(game), LD_LIBRARY_PATH='/firmware/libs'),
                           text=True, capture_output=True, timeout=5)
        assert r.returncode == 0 and 'inherited_libraries=/firmware/libs' in r.stdout
        assert '--library-path' in r.stdout
        # A missing Data tree must leave a persistent breadcrumb next to the entry.
        game.rename(game.with_name('saved-game'))
        r = subprocess.run(['sh', str(entry)], env=env, capture_output=True, text=True, timeout=5)
        text = (ports/'Minecraft Bedrock bootstrap.log').read_text()
        assert r.returncode == 1 and 'Port directory missing' in text
        assert 'exit_code=1' in text
    print('PASS POSIX bootstrap: Python errors, partial runtime, discovery errors, child exits, independent entries, private Bash environment')


if __name__ == '__main__': main()
