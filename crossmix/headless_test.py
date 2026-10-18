#!/usr/bin/env python3
"""Exercise the production session with real ARM64 Weston/Xwayland via QEMU.
The game is deliberately replaced by xdpyinfo; no GPU/game validation is claimed.
"""
import json, os, resource, shutil, subprocess, tempfile
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
ROOT=Path(__file__).resolve().parents[1]
C=ROOT/'crossmix'
G=ROOT/'dist/stage/Data/ports/minecraftbedrock'
D=G/'crossmix/runtime/debian';W=G/'crossmix/runtime/weston'


def main():
    with tempfile.TemporaryDirectory(prefix='mcpe headless production ') as temp:
        temp=Path(temp);game=temp/'game';adapter=game/'crossmix'
        (adapter/'runtime').mkdir(parents=True);(game/'logs').mkdir()
        (adapter/'runtime/weston').symlink_to(W)
        (adapter/'runtime/debian').symlink_to(D)
        for name in ('session.sh','prepare_x11.py','session_report.py','xwayland.sh','xkbcomp.sh'):
            shutil.copyfile(C/name,adapter/name);(adapter/name).chmod(0o755)
        # Only the host execution boundary is substituted for QEMU.
        # All production session/config/Xwayland/XKB orchestration runs unchanged.
        helper=adapter/'native-run.sh'
        helper.write_text('''#!/usr/bin/env python3
import os,sys
from pathlib import Path
g=Path(os.environ['GAMEDIR']);w=g/'crossmix/runtime/weston';d=g/'crossmix/runtime/debian'
lp=':'.join(map(str,[d/'lib/aarch64-linux-gnu',d/'usr/lib/aarch64-linux-gnu',Path(os.environ['MCPE_TEST_SOURCE_GAME'])/'libs.aarch64',w/'lib_aarch64']))
args=sys.argv[1:]
if Path(args[0]).name=='mcpelauncher-client':
 (g/'session-record').write_text(os.environ['MCPE_SESSION_DIR'])
 args=[str(w/'tools/xdpyinfo')]
env=dict(os.environ,LD_LIBRARY_PATH='/nonexistent');env.pop('LD_PRELOAD',None)
os.execvpe('qemu-aarch64-static',['qemu-aarch64-static',str(d/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1'),'--inhibit-cache','--library-path',lp,*args],env)
''');helper.chmod(0o755)
        (adapter/'probe.py').write_text('print("CRUSTY_LIBSDL=/fixture/sdl\\nCRUSTY_LIBEGL=/fixture/egl\\nCRUSTY_LIBGLES=/fixture/gles")\n')
        env=dict(os.environ,GAMEDIR=str(game),MCVER_OVERRIDE='fixture',MCPE_CARD_ROOT=str(temp),MCPE_TEST_SOURCE_GAME=str(G))
        result=subprocess.run(['bash',str(adapter/'session.sh')],env=env,capture_output=True,text=True,timeout=20)
        logs='\n'.join(p.read_text() for p in (game/'logs').glob('*.log'))
        assert result.returncode==0,(result.returncode,result.stderr,result.stdout,logs)
        assert 'dimensions:' in logs,logs
        assert not Path((game/'session-record').read_text()).exists(),'session temp directory leaked'
        evidence={'passed':True,'session_scripts':'production','weston_xwayland':'real ARM64 binaries under QEMU','client':'xdpyinfo substituted for Minecraft','hardware_tested':False,'graphics_rendered':False,'log':logs}
        (ROOT/'dist/headless-results.json').write_text(json.dumps(evidence,indent=2)+'\n')
        print('PASS production session + real ARM64 Weston/Xwayland handshake; no GPU/game validation')


if __name__=='__main__':main()
