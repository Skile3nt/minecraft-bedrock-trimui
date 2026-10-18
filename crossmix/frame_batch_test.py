#!/usr/bin/env python3
"""Synthetic verified-caller batches, native EGL dimensions and ABI; no GPU."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

C=Path(__file__).resolve().parent


def run(args,**kw):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=15,**kw)
    assert p.returncode==0,(p.stdout,p.stderr);return p.stdout


def main():
    with tempfile.TemporaryDirectory() as t:
        t=Path(t)
        (t/'backend.c').write_text(r'''
int calls;
void _SDL_GL_SwapWindow(void*w){calls++;}
void *d(void){return (void*)1;} void *s(int f){return (void*)2;}
unsigned q(void*d,void*s,int a,int*v){*v=a==0x3057?1024:576;return 1;}
void size(void*w,int*x,int*y){*x=1024;*y=576;}
void *__eglGetCurrentDisplay=d,*__eglGetCurrentSurface=s,*__eglQuerySurface=q,*__SDL_GL_GetDrawableSize=size;
void glGetIntegerv(unsigned e,int*v){if(e==0x0BA2){v[0]=v[1]=0;v[2]=1024;v[3]=576;}else *v=0;}
''')
        (t/'crusty.c').write_text('void _SDL_GL_SwapWindow(void*);\nvoid swap_buffers(void){_SDL_GL_SwapWindow((void*)1);}\n')
        (t/'check.c').write_text('extern int calls;void swap_buffers(void);int main(){for(int i=0;i<500;i++)swap_buffers();return calls==500?0:1;}')
        for cc,arch in [('gcc','host'),('aarch64-linux-gnu-gcc','arm64')]:
            d=t/arch;d.mkdir()
            run([cc,'-shared','-fPIC',t/'backend.c','-o',d/'backend.so'])
            run([cc,'-shared','-fPIC','-O0',t/'crusty.c',d/'backend.so','-o',d/'libcrusty.so'])
            run([cc,t/'check.c',d/'libcrusty.so',d/'backend.so','-Wl,-rpath,'+str(d),'-o',d/'check'])
            run([cc,'-shared','-fPIC','-O2','-Wall','-Wextra','-Werror',C/'sdl-trace.c','-ldl','-o',d/'trace.so'])
            run([cc,'-shared','-fPIC','-O2','-Wall','-Wextra','-Werror','-DMCPE_FRAME_METRICS_MAX_BATCHES=1',
                 C/'sdl-trace.c','-ldl','-o',d/'trace-limited.so'])
            path=d/'frames.jsonl';env=dict(os.environ,MCPE_BENCH_FILE=str(path))
            if arch=='host':args=[d/'check'];env['LD_PRELOAD']=str(d/'trace.so')
            else:
                runtime=C.parent/'dist/stage/Data/ports/minecraftbedrock/crossmix/runtime/debian'
                args=['qemu-aarch64-static',runtime/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1',
                      '--library-path',str(runtime/'lib/aarch64-linux-gnu'), '--preload',d/'trace.so',d/'check']
            run(args,env=env)
            rows=[json.loads(s) for s in path.read_text().splitlines()]
            assert len(rows)==2 and all(r['intervals']==240 for r in rows)
            assert all(r['egl_surface']==[1024,576] and r['viewport']==[0,0,1024,576] and r['fbo']==0 for r in rows)
            assert all(r['clock_domain']=='CLOCK_MONOTONIC; suspend excluded' and
                       r['monotonic_seconds']>0 and r['uptime']>0 for r in rows)
            limited=d/'frames-limited.jsonl';limited_env=dict(env,MCPE_BENCH_FILE=str(limited))
            if arch=='host':limited_args=args;limited_env['LD_PRELOAD']=str(d/'trace-limited.so')
            else:
                limited_args=args.copy();limited_args[limited_args.index('--preload')+1]=str(d/'trace-limited.so')
            run(limited_args,env=limited_env)
            limited_rows=[json.loads(s) for s in limited.read_text().splitlines()]
            assert len(limited_rows)==1 and limited_rows[0]['intervals']==240
            assert limited.stat().st_size<2048
    print('PASS bounded frame batches: verified Crusty caller, 500 swaps preserved, 1-batch cap; host + ARM64 QEMU, no physical FPS')


if __name__=='__main__':main()
