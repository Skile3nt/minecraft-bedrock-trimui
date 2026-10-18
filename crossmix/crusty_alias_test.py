#!/usr/bin/env python3
"""Reproduce FAT-dereferenced Crusty aliases with real ARM64 Crusty under QEMU."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from crusty_routing_test import ROOT, C, G, D, W, CRUSTY, run


def main():
    symbols=run(['aarch64-linux-gnu-nm','-D',CRUSTY]).stdout
    results=[]
    with tempfile.TemporaryDirectory(prefix='mcpe-crusty-alias-') as tmp:
        p=Path(tmp);link=p/'link';link.mkdir()
        for kind,prefix in [('EGL','__egl'),('SDL2','__SDL')]:
            text='#include <dlfcn.h>\n#include <stdlib.h>\n'
            for suffix in re.findall(r' B '+prefix+r'(\w+)',symbols):
                name=('egl' if kind=='EGL' else 'SDL')+suffix
                text+=('int eglChooseConfig(void*a,void*b,void*c,int d,int*e){if(e)*e=1;return 77;}\n'
                       if name=='eglChooseConfig' else 'void *'+name+'(){return 0;}\n')
            if kind=='SDL2':
                text+='int fixture_probe(void){void*h=dlopen(getenv("CRUSTY_LIBEGL"),RTLD_NOW);int(*f)(void*,void*,void*,int,int*)=dlsym(h,"eglChooseConfig");int n=0;return f?f(0,0,0,0,&n):-1;}\n'
            (p/(kind+'.c')).write_text(text)
            run(['aarch64-linux-gnu-gcc','-shared','-fPIC',p/(kind+'.c'),'-o',p/('lib'+kind+'-fixture.so'),'-ldl'])
        (p/'dummy.c').write_text('int fixture_dummy(void){return 0;}\n')
        run(['aarch64-linux-gnu-gcc','-shared','-fPIC',p/'dummy.c','-o',p/'libGLESv2.so'])
        # A native-EGL soname at link time, copied Crusty under that filename at
        # run time: exactly the released client's DT_NEEDED libEGL.so.1 path.
        run(['aarch64-linux-gnu-gcc','-shared','-fPIC',p/'dummy.c','-Wl,-soname,libEGL.so.1','-o',link/'libEGL.so.1'])
        (p/'check.c').write_text(r'''#define _GNU_SOURCE
#include <dlfcn.h>
#include <link.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int objects=0;
static int inspect(struct dl_phdr_info*i,size_t n,void*d){if(strstr(i->dlpi_name,"libcrusty.so")||strstr(i->dlpi_name,"libEGL.so.1")||strstr(i->dlpi_name,"libCRU.so"))objects++;return 0;}
int main(){void*(*real_open)(const char*,int)=dlvsym(RTLD_DEFAULT,"dlopen","GLIBC_2.34");
void*h=real_open(getenv("CRUSTY_LIBSDL"),RTLD_NOW);int(*probe)(void)=dlsym(h,"fixture_probe");
int(*classify)(void*)=dlsym(RTLD_DEFAULT,"call_from_backend");
void*app=dlopen(getenv("CRUSTY_LIBEGL"),RTLD_NOW);int(*choose)(void*,void*,void*,int,int*)=dlsym(app,"eglChooseConfig");
int result=probe(),n=0,appresult=choose(0,0,0,0,&n);dl_iterate_phdr(inspect,0);
printf("CLASSIFIED=%d ROUTED_RESULT=%d APP_RESULT=%d CRUSTY_OBJECTS=%d\n",classify(probe),result,appresult,objects);return 0;}
''')
        run(['aarch64-linux-gnu-gcc',p/'check.c','-L'+str(link),'-Wl,--no-as-needed','-l:libEGL.so.1','-o',p/'check','-ldl'])
        assert 'libEGL.so.1' in run(['aarch64-linux-gnu-readelf','-d',p/'check']).stdout
        run(['aarch64-linux-gnu-gcc','-shared','-fPIC','-O2',C/'isolate-crusty.c','-o',p/'bridge.so','-ldl'])
        for aliases in ('fat-copies','session-symlinks'):
            a=p/aliases;a.mkdir();session=a/'session';session.mkdir()
            for name in ('libEGL.so','libEGL.so.1','libCRU.so','libCRU.so.1'):
                if aliases=='fat-copies':shutil.copyfile(CRUSTY,a/name)
                else:(a/name).symlink_to(CRUSTY)
            lp=':'.join(map(str,[a,p,D/'lib/aarch64-linux-gnu',D/'usr/lib/aarch64-linux-gnu',W/'lib_aarch64',G/'libs.aarch64']))
            env=dict(os.environ,CRUSTY_LIBSDL=str(p/'libSDL2-fixture.so'),CRUSTY_LIBEGL=str(p/'libEGL-fixture.so'),MCPE_SESSION_DIR=str(session))
            env.pop('LD_PRELOAD',None)
            out=run(['qemu-aarch64-static',D/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1','--inhibit-cache','--library-path',lp,
                     '--preload',str(p/'bridge.so')+':'+str(CRUSTY),p/'check'],env=env)
            expected='CLASSIFIED=1 ROUTED_RESULT='+('0' if aliases=='fat-copies' else '77')+' APP_RESULT=0'
            assert expected in out.stdout,out.stdout
            if aliases=='session-symlinks':assert 'CRUSTY_OBJECTS=1' in out.stdout,out.stdout
            else:assert re.search(r'CRUSTY_OBJECTS=[23]',out.stdout),out.stdout
            results.append({'aliases':aliases,'stdout':out.stdout,'stderr':out.stderr})
    (ROOT/'dist/crusty-alias-results.json').write_text(json.dumps({'passed':True,'hardware_tested':False,
        'graphics_rendered':False,'cases':results},indent=2)+'\n')
    print('PASS real ARM64 Crusty: copied aliases reproduce SDL facade despite correct classification; session symlinks restore native route and preserve app facade')


if __name__=='__main__':main()
