#!/usr/bin/env python3
"""Use pinned ARM64 Crusty under QEMU to reproduce/fix backend misclassification.
Synthetic EGL/SDL libraries only: no framebuffer, GPU, Minecraft or account data.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/'crossmix';G=ROOT/'dist/stage/Data/ports/minecraftbedrock'
D=G/'crossmix/runtime/debian';W=G/'crossmix/runtime/weston'
CRUSTY=W/'lib_aarch64/graphics/crusty_x11egl/libcrusty.so'


def run(args, **kwargs):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=15,**kwargs)
    assert p.returncode==0,(args,p.returncode,p.stdout,p.stderr)
    return p


def main():
    symbols=run(['aarch64-linux-gnu-nm','-D',CRUSTY]).stdout
    evidence=[]
    with tempfile.TemporaryDirectory(prefix='mcpe-crusty-') as tmp:
        p=Path(tmp)
        for kind,prefix in [('EGL','__egl'),('SDL2','__SDL')]:
            names=re.findall(r' B '+prefix+r'(\w+)',symbols)
            text='#include <dlfcn.h>\n#include <stdlib.h>\n'
            for name in names:
                name=('egl' if kind=='EGL' else 'SDL')+name
                text+=('int eglChooseConfig(void*a,void*b,void*c,int d,int*e){if(e)*e=1;return 77;}\n'
                    if name=='eglChooseConfig' else 'void *'+name+'(){return 0;}\n')
            if kind=='SDL2':
                text+='int fixture_probe(void){void*h=dlopen(getenv("CRUSTY_LIBEGL"),RTLD_NOW);int(*f)(void*,void*,void*,int,int*)=dlsym(h,"eglChooseConfig");int n=0;return f(0,0,0,0,&n);}\n'
            (p/(kind+'.c')).write_text(text)
        (p/'GLES.c').write_text('int fixture_dummy(void){return 0;}\n')
        (p/'check.c').write_text('''#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
int main(){void*(*real_open)(const char*,int)=dlvsym(RTLD_DEFAULT,"dlopen","GLIBC_2.34");void*h=real_open(getenv("CRUSTY_LIBSDL"),RTLD_NOW);int(*probe)(void)=dlsym(h,"fixture_probe");int(*classify)(void*)=dlsym(RTLD_DEFAULT,"call_from_backend");int cl=classify(probe),result=probe();void*app=dlopen(getenv("CRUSTY_LIBEGL"),RTLD_NOW);int(*choose)(void*,void*,void*,int,int*)=dlsym(app,"eglChooseConfig");int n=0;printf("CLASSIFIED=%d ROUTED_RESULT=%d APP_CLASSIFIED=%d APP_RESULT=%d\\n",cl,result,classify(main),choose(0,0,0,0,&n));return 0;}
''')
        # Build the exact previously installed bridge, not a hand-made mock bug.
        (p/'old.c').write_bytes(subprocess.check_output(['git','show','b76ffcf:crossmix/isolate-crusty.c'],cwd=ROOT))
        for name,source in [('old',p/'old.c'),('fixed',C/'isolate-crusty.c')]:
            run(['aarch64-linux-gnu-gcc','-shared','-fPIC','-O2','-Wall','-Wextra',source,'-o',p/(name+'.so'),'-ldl'])
        run(['aarch64-linux-gnu-gcc','-shared','-fPIC','-Wl,-z,separate-code',p/'EGL.c','-o',p/'libEGL-fixture.so'])
        run(['aarch64-linux-gnu-gcc','-shared','-fPIC',p/'GLES.c','-o',p/'libGLESv2.so'])
        run(['aarch64-linux-gnu-gcc',p/'check.c','-o',p/'check','-ldl'])
        for separate in (False,True):
            sdl=p/('libSDL2-'+str(int(separate))+'.so')
            run(['aarch64-linux-gnu-gcc','-shared','-fPIC','-Wl,-z,'+('separate-code' if separate else 'noseparate-code'),p/'SDL2.c','-o',sdl,'-ldl'])
            for bridge in ('old','fixed'):
                session=p/(bridge+str(int(separate)));session.mkdir()
                lp=':'.join(map(str,[p,D/'lib/aarch64-linux-gnu',D/'usr/lib/aarch64-linux-gnu',W/'lib_aarch64',G/'libs.aarch64']))
                env=dict(os.environ,CRUSTY_LIBSDL=str(sdl),CRUSTY_LIBEGL=str(p/'libEGL-fixture.so'),MCPE_SESSION_DIR=str(session))
                env.pop('LD_PRELOAD',None)
                result=run(['qemu-aarch64-static',D/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1','--inhibit-cache','--library-path',lp,'--preload',str(p/(bridge+'.so'))+':'+str(CRUSTY),p/'check'],env=env)
                expected='CLASSIFIED=0 ROUTED_RESULT=0' if separate and bridge=='old' else 'CLASSIFIED=1 ROUTED_RESULT=77'
                assert expected+' APP_CLASSIFIED=0 APP_RESULT=0' in result.stdout,result.stdout
                evidence.append({'separate_code':separate,'bridge':bridge,'stdout':result.stdout,'stderr':result.stderr})
        assert ' dlopen' not in run(['aarch64-linux-gnu-nm','-D','--defined-only',p/'fixed.so']).stdout
    (ROOT/'dist/crusty-routing-results.json').write_text(json.dumps({'passed':True,'hardware_tested':False,'graphics_rendered':False,'cases':evidence},indent=2)+'\n')
    print('PASS real ARM64 Crusty: original separate-code failure, corrected native routing, normal layout and application facade preserved')


if __name__=='__main__':main()
