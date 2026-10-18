#!/usr/bin/env python3
"""Short host/regression/QEMU checks; no TrimUI GPU test claims."""
import ast, hashlib, importlib.util, json, os, shutil, subprocess, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=ROOT/'crossmix'
GAME=ROOT/'dist/stage/Data/ports/minecraftbedrock'
D=GAME/'crossmix/runtime/debian';W=GAME/'crossmix/runtime/weston'
checks=[]

def run(args, **kwargs):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=kwargs.pop('timeout',30),**kwargs)
    if r.returncode: raise AssertionError(str(args)+'\n'+r.stdout+'\n'+r.stderr)
    return r


def syntax():
    for p in C.rglob('*.py'): ast.parse(p.read_text())
    for p in [*C.glob('*.sh'),ROOT/'portmaster/minecraftbedrock/Minecraft Bedrock.sh',*(ROOT/'portmaster/minecraftbedrock/minecraftbedrock').glob('*.sh')]:
        run(['bash','-n',p])
    for p in [C/'entry.sh', C/'gpu-test.sh', C/'status.sh', *list((C/'bin').iterdir())]:
        run(['sh', '-n', p])
    run(['git','diff','--check'],cwd=ROOT)


def regression():
    for name in ['test_platform.sh','test_abi.sh','test_audio.sh','test_performance.sh','test_launcher_early_exit.sh']:
        if name=='test_audio.sh':
            run(['bash','-c','pidof() { return 1; }; pactl() { return 1; }; source "$0"',ROOT/'tests'/name],cwd=ROOT,timeout=45)
        else: run(['bash',ROOT/'tests'/name],cwd=ROOT,timeout=45)


def synthetic_crossmix():
    with tempfile.TemporaryDirectory() as t:
        t=Path(t)
        for name in ['proc/device-tree','etc','dev','sys/class/graphics/fb0','dev/snd']:(t/name).mkdir(parents=True,exist_ok=True)
        (t/'proc/device-tree/model').write_bytes(b'TrimUI Smart Pro\0')
        (t/'proc/device-tree/compatible').write_bytes(b'arm,sun50iw10p1\0')
        (t/'proc/meminfo').write_text('MemTotal: 1024000 kB\n')
        (t/'etc/os-release').write_text('NAME="Tina Linux"\n')
        for name in ['dev/pvrsrvkm','dev/disp','dev/fb0']:(t/name).touch()
        (t/'sys/class/graphics/fb0/virtual_size').write_text('1280,1440\n')
        script='''source "$1/lib/platform.sh"
MCPE_PROBE_ROOT="$2" MCPE_TEST_ARCH=aarch64 MCPE_TEST_COMPOSITOR=none MCPE_TEST_FB_MODE=1280x720 MCPE_CFW_OVERRIDE=crossmix MCPE_GRAPHICS_BACKEND=mali mcpe_probe_platform "$2/resolved.env"
source "$2/resolved.env"
[ "$MCPE_CFW" = crossmix ] && [ "$MCPE_HOST_PROFILE" = trimui_a133 ] && [ "$MCPE_ACTIVE_HEIGHT" = 720 ] && [ "$MCPE_HAS_DRM" = 0 ] && [ "$MCPE_GRAPHICS_BACKEND_RESOLVED" = mali ]
'''
        run(['bash','-c',script,'test',GAME,t])


def probe_abi():
    spec=importlib.util.spec_from_file_location('crossmix_probe',C/'probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    with tempfile.TemporaryDirectory() as t:
        t=Path(t);lib=t/'System/lib';lib.mkdir(parents=True)
        before=os.environ.get('MCPE_CARD_ROOT');os.environ['MCPE_CARD_ROOT']=str(t)
        try:
            for name in ['libSDL2-2.0.so.0','libEGL.so.1','libGLESv2.so.2']:
                h=bytearray(64);h[:5]=b'\x7fELF\x02';h[18:20]=(62).to_bytes(2,'little');(lib/name).write_bytes(h)
            assert not m.libraries(), 'x86_64 library accepted'
            for p in lib.iterdir():
                h=bytearray(p.read_bytes());h[18:20]=(183).to_bytes(2,'little');p.write_bytes(h)
            assert len(m.libraries())==3
        finally:
            if before is None:os.environ.pop('MCPE_CARD_ROOT')
            else:os.environ['MCPE_CARD_ROOT']=before


def isolate_aliases():
    with tempfile.TemporaryDirectory() as t:
        t=Path(t)
        (t/'backend.c').write_text('#include <stddef.h>\nvoid *load_lib_local(const char *a,const char *b){return NULL;}\nvoid *fixture_load(const char *key){return load_lib_local("/invalid-fallback",key); }\n')
        (t/'target.c').write_text('int fixture_marker(void){return 42;}\n')
        (t/'check.c').write_text('#include <dlfcn.h>\nint main(int c,char **v){void *b=dlopen(v[1],RTLD_NOW);if(!b)return 1;void *(*load)(const char *)=dlsym(b,"fixture_load");void *h=load("CRUSTY_LIBSDL");if(!h)return 2;int (*marker)(void)=dlsym(h,"fixture_marker");if(!marker||marker()!=42)return 3;return load("CRUSTY_LIBEGL")?0:4;}\n')
        for arch,compiler in [('host','gcc'),('arm64','aarch64-linux-gnu-gcc')]:
            out=t/arch;out.mkdir()
            run([compiler,'-shared','-fPIC','-O2',C/'isolate-crusty.c','-o',out/'isolate.so','-ldl'])
            for source in ('backend','target'):
                run([compiler,'-shared','-fPIC',t/(source+'.c'),'-o',out/(source+'.so')])
            run([compiler,t/'check.c','-o',out/'check','-ldl'])
            env=dict(os.environ,MCPE_SESSION_DIR=str(out),CRUSTY_LIBSDL=str(out/'target.so'),CRUSTY_LIBEGL=str(out/'target.so'))
            if arch=='host':
                env['LD_PRELOAD']=str(out/'isolate.so')
                run([out/'check',out/'backend.so'],env=env)
            else:
                env.pop('LD_PRELOAD',None)
                lp=':'.join(map(str,[D/'lib/aarch64-linux-gnu',D/'usr/lib/aarch64-linux-gnu']))
                run(['qemu-aarch64-static',D/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1','--inhibit-cache','--library-path',lp,'--preload',out/'isolate.so',out/'check',out/'backend.so'],env=env)
            assert (out/'CRUSTY_LIBSDL64.so').is_symlink()
            assert (out/'CRUSTY_LIBEGL64.so').is_symlink()
            assert ' dlopen' not in run(['nm','-D','--defined-only',out/'isolate.so']).stdout,'general dlopen hook masks Crusty callers'



def archive():
    zpath=ROOT/('dist/minecraft-bedrock-crossmix-'+(C/'ADAPTATION_VERSION').read_text().strip()+'.zip')
    with zipfile.ZipFile(zpath) as z:
        assert z.testzip() is None
        assert 'Roms/PORTS/Minecraft Bedrock CrossMix.sh' in z.namelist()
        # Entry failure text evolves; preserve the visual launcher and wrappers.
        with zipfile.ZipFile(ROOT/'dist/minecraft-bedrock-crossmix-0.1.1-experimental-probe-fix.zip') as old:
            protected = ['Data/ports/minecraftbedrock/crossmix/'+n for n in
                          ['love-run.sh','love.txt','upstream-entry.sh','bin/bash','bin/python3']]
            for name in protected:assert z.read(name)==old.read(name), 'Validated launcher changed: '+name
        for label,mode in [('CrossMix','${1:-}'),('Diagnostics','--diagnose'),('GPU Test','--graphics-test'),('SDL Test','--sdl-test'),('Input Test','--input-test'),('Original','--original'),('No Particles','--no-particles'),('Performance','--performance'),('No Particles Assets','--no-particles-assets')]:
            expected=(C/'entry.sh').read_text().replace('entry_mode=${1:-}', 'entry_mode='+mode,1)
            assert z.read('Roms/PORTS/Minecraft Bedrock '+label+'.sh').decode()==expected
        assert 'Roms/PORTS/Minecraft Bedrock Diagnostics.sh' in z.namelist()
        assert '=== CrossMix bootstrap' in z.read('Roms/PORTS/Minecraft Bedrock Diagnostics.sh').decode()
        info=z.getinfo('Data/ports/minecraftbedrock/crossmix/bin/bash')
        assert (info.external_attr>>16)&0o111, 'private Bash wrapper must be executable'
        assert not any(n.lower().endswith(('.apk','.apks','.xapk','.mcworld')) or n.endswith('/libminecraftpe.so') for n in z.namelist())
        manifest=json.loads(z.read('Data/ports/minecraftbedrock/crossmix/MANIFEST.json'))
        for name,sha in manifest['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==sha,name
        for info in z.infolist():assert ((info.external_attr>>16)&0o170000)!=0o120000,'ZIP requires symlinks'


def qemu():
    spec=importlib.util.spec_from_file_location('crossmix_build',C/'build.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    fixture=ROOT/'dist/host-fixtures';fixture.mkdir(exist_ok=True)
    for package in json.loads((C/'test-debian-lock.json').read_text()):
        deb=b.fetch(ROOT.parent/'downloads',Path(package['Filename']).name,'https://deb.debian.org/debian/'+package['Filename'],package['SHA256'])
        b.extract_deb(deb,fixture)
    lp=':'.join(map(str,[fixture/'usr/lib/aarch64-linux-gnu',D/'lib/aarch64-linux-gnu',D/'usr/lib/aarch64-linux-gnu',GAME/'libs.aarch64',W/'lib_aarch64']))
    command=['qemu-aarch64-static',D/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1','--inhibit-cache','--library-path',lp]
    r=subprocess.run(list(map(str,[*command,GAME/'bin/mcpelauncher-client','--help'])),capture_output=True,text=True,timeout=10)
    assert r.returncode==1 and 'Program Help' in r.stdout and not r.stderr,(r.returncode,r.stdout,r.stderr)
    r=run([*command,D/'bin/bash','-c','a=(ok); [[ ${a[0]} == ok ]] && printf "GNU Bash %s\\n" "$BASH_VERSION"']);assert 'GNU Bash 5.' in r.stdout
    r=run([*command,W/'wp_weston','--version']);assert 'weston' in r.stdout
    lp2=str(D/'usr/lib/aarch64-linux-gnu')+':'+str(D/'lib/aarch64-linux-gnu')+':'+str(W/'lib_aarch64')
    r=run(['qemu-aarch64-static',D/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1','--inhibit-cache','--library-path',lp2,W/'bin/Xwayland','-version']);assert 'xwayland' in (r.stdout+r.stderr).lower()


def session_cleanup():
    with tempfile.TemporaryDirectory(prefix='mcpe session test ') as t:
        t=Path(t);g=t/'game';(g/'crossmix/runtime/weston').mkdir(parents=True);(g/'logs').mkdir()
        shutil.copyfile(C/'session.sh',g/'crossmix/session.sh')
        shutil.copyfile(C/'prepare_x11.py',g/'crossmix/prepare_x11.py')
        shutil.copyfile(C/'session_report.py',g/'crossmix/session_report.py')
        (g/'crossmix/probe.py').write_text('print("CRUSTY_LIBSDL=/fixture/sdl\\nCRUSTY_LIBEGL=/fixture/egl\\nCRUSTY_LIBGLES=/fixture/gles")\n')
        mock=g/'crossmix/native-run.sh'
        mock.write_text('''#!/usr/bin/env python3
import os,sys,socket,time
from pathlib import Path
if Path(sys.argv[1]).name=='wp_weston':
 s=socket.socket(socket.AF_UNIX);s.bind(os.environ['XDG_RUNTIME_DIR']+'/mcpe-wayland')
 print('xserver listening on display :42',flush=True)
 while True:time.sleep(.1)
else:
 Path(os.environ['GAMEDIR']+'/session-record').write_text(os.environ['MCPE_SESSION_DIR'])
 sys.exit(42)
''');mock.chmod(0o755)
        env=dict(os.environ,GAMEDIR=str(g),MCVER_OVERRIDE='fixture',MCPE_CARD_ROOT=str(t))
        r=subprocess.run(['bash',str(g/'crossmix/session.sh')],env=env,capture_output=True,text=True,timeout=10)
        assert r.returncode==42,(r.returncode,r.stderr,r.stdout)
        assert not Path((g/'session-record').read_text()).exists(), 'session temp directory leaked'


def headless_handshake():
    run(['python3','-B',C/'headless_test.py'],timeout=20)


def crusty_aliases():
    run(['python3','-B',C/'crusty_alias_test.py'])


def main():
    crusty_aliases();checks.append('real ARM64 copied Crusty aliases and single-object fix');print('PASS '+checks[-1],flush=True)
    for name,f in [('syntax',syntax),('particle profiles and rollback',lambda:run(['python3','-B',C/'performance_profile_test.py'])),('thread-level CPU telemetry',lambda:run(['python3','-B',C/'session_metrics_test.py'])),('verified frame batches',lambda:run(['python3','-B',C/'frame_batch_test.py'])),('native input bridge and ARM64 ABI',lambda:run(['python3','-B',C/'input_bridge_test.py'])),('safe telemetry and input capture',lambda:run(['python3','-B',C/'input_metrics_test.py'])),('SDL trace and ARM64 binding audit',lambda:run(['python3','-B',C/'sdl_trace_test.py'])),('SDL A/B session isolation and stale reports',lambda:run(['python3','-B',C/'sdl_session_test.py'])),('real ARM64 Crusty backend routing',lambda:run(['python3','-B',C/'crusty_routing_test.py'])),('first error and process reporting',lambda:run(['python3','-B',C/'session_report_test.py'])),('X11 socket preparation and session failure regression',lambda:run(['python3','-B',C/'session_test.py'])),('POSIX bootstrap failure injection',lambda:run(['python3','-B',C/'bootstrap_test.py'])),('captured TrimUI probe policy',lambda:run(['python3','-B',C/'probe_policy_test.py'])),('EGL/GLES mock loader regression',lambda:run(['python3','-B',C/'graphics_test.py'])),('upstream regressions (5 suites)',regression),('synthetic CrossMix profile',synthetic_crossmix),('probe ABI rejection',probe_abi),('isolated Crusty loader aliases',isolate_aliases),('ZIP and file checksums',archive),('ARM64 QEMU loader checks',qemu),('private session cleanup and exit status',session_cleanup),('real ARM64 Weston/Xwayland headless handshake',headless_handshake)]:
        f();checks.append(name);print('PASS '+name,flush=True)
    (ROOT/'dist/test-results.json').write_text(json.dumps({'passed':checks,'hardware_tested':False,'graphics_rendered':False},indent=2)+'\n')


if __name__=='__main__':main()
