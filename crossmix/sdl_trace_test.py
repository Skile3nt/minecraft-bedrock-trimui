#!/usr/bin/env python3
"""Failure injection and real ARM64 Crusty binding observation, never GPU proof."""
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile

C=Path(__file__).resolve().parent
ROOT=C.parent
G=ROOT/'dist/stage/Data/ports/minecraftbedrock'
D=G/'crossmix/runtime/debian'; W=G/'crossmix/runtime/weston'


def run(args, **kwargs):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=20,**kwargs)
    assert p.returncode==0,(args,p.returncode,p.stdout,p.stderr)
    return p


def build_audit(compiler, dest):
    run([compiler,'-O2','-fPIC','-shared','-nostdlib','-fno-builtin','-fno-stack-protector',
         '-Wall','-Wextra','-Werror',C/'egl-bind-audit.c','-o',dest])
    assert not run(['nm','-u',dest]).stdout.strip(), 'audit callback has libc dependencies'


def main():
    evidence=[]
    with tempfile.TemporaryDirectory(prefix='mcpe-sdl-trace-') as temp:
        p=Path(temp)
        (p/'fixture.c').write_text(r'''
#include <stdlib.h>
#include <stdio.h>
int loads=0;
const char *error(void){return "fixture SDL error already consumed EGL error";}
unsigned eglerror(void){return 0x3000;}
int init(unsigned f){return getenv("FAIL_INIT")?47:0;}
void *window(const char*t,int x,int y,int w,int h,unsigned f){return getenv("FAIL_WINDOW")?0:(void*)1;}
void *context(void*w){return getenv("FAIL_CONTEXT")?0:(void*)2;}
const char *driver(void){return "FIXTURE_NO_GPU";}
void version(unsigned char*v){v[0]=2;v[1]=26;v[2]=5;}
void *__SDL_GetError=error,*__eglGetError=eglerror,*__SDL_Init=init;
void *__SDL_CreateWindow=window,*__SDL_GL_CreateContext=context;
void *__SDL_GetCurrentVideoDriver=driver,*__SDL_GetVersion=version;
int _SDL_Init(unsigned f){return init(f);}
void *_SDL_CreateWindow(const char*t,int x,int y,int w,int h,unsigned f){return window(t,x,y,w,h,f);}
void *_SDL_GL_CreateContext(void*w){return context(w);}
void _SDL_GL_SwapWindow(void*w){loads+=10;}
int SDL_GL_LoadLibrary(const char*p){loads++;return 0;}
unsigned eglChooseConfig(void*d,const int*a,void**c,int n,int*count){*count=1;return 77;}
unsigned _eglInitialize(void*d,int*a,int*b){return 1;}
void *_eglCreateContext(void*d,void*c,void*s,const int*a){return (void*)3;}
void *_eglCreateWindowSurface(void*d,void*c,void*w,const int*a){return (void*)4;}
unsigned _eglGetError(void){return 0x3005;}
''')
        (p/'check.c').write_text(r'''
#include <stdio.h>
extern int loads;
int _SDL_Init(unsigned);
void *_SDL_CreateWindow(const char*,int,int,int,int,unsigned);
void *_SDL_GL_CreateContext(void*);
unsigned eglChooseConfig(void*,const int*,void**,int,int*);
unsigned _eglInitialize(void*,int*,int*);
void *_eglCreateContext(void*,void*,void*,const int*);
void *_eglCreateWindowSurface(void*,void*,void*,const int*);
unsigned _eglGetError(void);
void _SDL_GL_SwapWindow(void*);
int main(){int i=_SDL_Init(32),n=0;void*w=_SDL_CreateWindow("fixture",0,0,1280,720,162),*c=_SDL_GL_CreateContext(w);
unsigned config=eglChooseConfig(0,0,0,0,&n);
_SDL_GL_SwapWindow(w);_SDL_GL_SwapWindow(w);
printf("init=%d window=%p context=%p loads=%d config=%u error=0x%x EGLinit=%u EGLcontext=%p EGLsurface=%p\n",i,w,c,loads,config,_eglGetError(),_eglInitialize(0,0,0),_eglCreateContext(0,0,0,0),_eglCreateWindowSurface(0,0,0,0));return 0;}
''')
        run(['gcc','-shared','-fPIC',p/'fixture.c','-o',p/'fixture.so'])
        run(['gcc',p/'check.c',p/'fixture.so','-Wl,-rpath,'+str(p),'-o',p/'check'])
        for compiler,arch in [('gcc','host'),('aarch64-linux-gnu-gcc','arm64')]:
            run([compiler,'-O2','-shared','-fPIC','-Wall','-Wextra','-Werror',C/'sdl-trace.c','-o',p/(arch+'-trace.so'),'-ldl'])
            run([compiler,'-O2','-shared','-fPIC','-Wall','-Wextra','-Werror',C/'input-bridge.c','-o',p/(arch+'-input.so'),'-ldl'])
            build_audit(compiler,p/(arch+'-audit.so'))
        versions=run(['aarch64-linux-gnu-readelf','--version-info',p/'arm64-trace.so']).stdout
        assert all(tuple(map(int,v.split('.'))) <= (2,36) for v in re.findall(r'Name: GLIBC_([0-9.]+)',versions)),versions
        env=dict(os.environ,LD_PRELOAD=str(p/'host-trace.so'),LD_AUDIT=str(p/'host-audit.so'),
            CRUSTY_LIBEGL='/fixture/EGL',SDL_VIDEO_EGL_DRIVER='/fixture/EGL',SDL_VIDEO_GL_DRIVER='/fixture/GLES')
        # Explicit EGL flag alone must never change the game path.
        for extras,expected in [({},'loads=20'),({'MCPE_SDL_PROBE_EXPLICIT_EGL':'1'},'loads=20'),
             ({'MCPE_GRAPHICS_PROBE':'1','MCPE_SDL_PROBE_EXPLICIT_EGL':'1'},'loads=21'),
             ({'FAIL_INIT':'1'},'init=47'),({'FAIL_WINDOW':'1'},'window=(nil)'),({'FAIL_CONTEXT':'1'},'context=(nil)')]:
            r=run([p/'check'],env=dict(env,**extras))
            assert expected in r.stdout and 'config=77 error=0x3005' in r.stdout,r.stdout
            assert 'native_SDL_version=2.26.5' in r.stderr
            assert 'binding symbol=eglChooseConfig' in r.stderr
            if any(k.startswith('FAIL_') for k in extras):
                assert 'SDL_GetError=fixture SDL error already consumed EGL error' in r.stderr
                assert 'terminal_eglGetError=0x3000 (after SDL consumed error)' in r.stderr
            evidence.append({'fixture':extras,'stdout':r.stdout})
        # Use the existing real Crusty regression, adding our observers to every
        # QEMU invocation. Expected old/fixed routing and app facade stay equal.
        wrapper=p/'bin';wrapper.mkdir()
        real_qemu=run(['sh','-c','command -v qemu-aarch64-static']).stdout.strip()
        script=wrapper/'qemu-aarch64-static'
        script.write_text('#!'+os.sys.executable+'\nimport os,sys\n'
            f'args=sys.argv[1:];i=args.index("--preload");v=args[i+1].split(":");v.insert(1,"{p}/arm64-trace.so");v.insert(1,"{p}/arm64-input.so");args[i+1]=":".join(v)\n'
            f'args[1:1]=["--audit","{p}/arm64-audit.so"]\n'
            f'os.execv({real_qemu!r},[{real_qemu!r},*args])\n')
        script.chmod(0o755)
        r=run(['python3','-B',C/'crusty_routing_test.py'],env=dict(os.environ,PATH=str(wrapper)+':'+os.environ['PATH']))
        routing=json.loads((ROOT/'dist/crusty-routing-results.json').read_text())
        for case in routing['cases']:
            assert 'CrossMix binding symbol=eglChooseConfig' in case['stderr'],case['stderr']
        evidence.append({'real_crusty_qemu':r.stdout,'cases':routing['cases']})
        # No session machinery/proprietary content is required to test the probe
        # missing-runtime failure. ARM64 --help is not a physical graphics test.
        run(['gcc','-O2','-Wall','-Wextra','-Werror',C/'sdl-session-probe.c','-o',p/'probe','-ldl'])
        result=subprocess.run([p/'probe'],capture_output=True,text=True,timeout=5)
        assert result.returncode==2 and 'probe_missing=init_backend' in result.stderr
    (ROOT/'dist/sdl-trace-results.json').write_text(json.dumps({'passed':True,'hardware_tested':False,
        'graphics_rendered':False,'cases':evidence},indent=2)+'\n')
    print('PASS SDL trace: returns/errors preserved; A/B isolated; dependency-free binding audit; real ARM64 Crusty routing unchanged under QEMU')


if __name__=='__main__':main()
