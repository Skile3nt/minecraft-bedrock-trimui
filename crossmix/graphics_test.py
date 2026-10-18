#!/usr/bin/env python3
"""Mock-only GLES loader checks: no framebuffer, native GPU or software renderer."""
import importlib.util, os, subprocess, tempfile
from pathlib import Path
from unittest.mock import patch
C=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('probe', C/'probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def run(args, **kw):
    r=subprocess.run(list(map(str,args)),text=True,capture_output=True,timeout=10,**kw)
    if r.returncode:raise AssertionError((args,r.stdout,r.stderr))
    return r


def main():
    with tempfile.TemporaryDirectory(prefix='mcpe graphics fixture ') as tmp:
        t=Path(tmp);sd=t/'System/lib';fw=t/'firmware';sd.mkdir(parents=True);fw.mkdir()
        header=bytearray(64);header[:5]=b'\x7fELF\x02';header[18:20]=(183).to_bytes(2,'little')
        for name in ('libSDL2.so','libGLESv2.so'):(sd/name).write_bytes(header)
        facade=sd/'libEGL.so.1';facade.write_bytes(header+b'gl4es_GetProcAddress\0')
        with patch.dict(os.environ,MCPE_CARD_ROOT=str(t)):
            # Compatibility discovery remains unchanged for the working menu.
            assert probe.libraries()['CRUSTY_LIBEGL']==str(facade)
            # A GL4ES facade cannot be silently accepted for the GPU test.
            assert 'CRUSTY_LIBEGL' not in probe.libraries(native=True)
            (sd/'libEGL.so').write_bytes(header)
            assert probe.libraries(native=True)['CRUSTY_LIBEGL']==str(sd/'libEGL.so')
        # Fake exports exercise error paths and cleanup; they never draw a frame.
        (t/'egl.c').write_text('void eglChooseConfig(void){} void eglGetDisplay(void){} void eglInitialize(void){} void eglCreateContext(void){} void eglGetError(void){}\n')
        (t/'gles.c').write_text('''const unsigned char *glGetString(unsigned a){return (const unsigned char *)"FIXTURE_NO_GPU";}
void glClearColor(float a,float b,float c,float d){} void glClear(unsigned a){} unsigned glGetError(void){return 0;}
''')
        (t/'sdl.c').write_text('''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int SDL_Init(unsigned x){return 0;} const char *SDL_GetError(void){return "fixture deliberate window failure";}
int SDL_GL_SetAttribute(int a,int b){return 0;} int SDL_GL_LoadLibrary(const char *p){return strcmp(p,getenv("CRUSTY_LIBEGL"))?1:0;}
void *SDL_CreateWindow(const char *a,int b,int c,int d,int e,unsigned f){return getenv("FIXTURE_FAIL_WINDOW")?NULL:(void*)1;}
void *SDL_GL_CreateContext(void *w){return (void*)2;} void SDL_GL_SwapWindow(void *w){}
void SDL_GL_DeleteContext(void *w){} void SDL_DestroyWindow(void *w){} void SDL_Delay(unsigned n){} void SDL_Quit(void){puts("fixture_cleanup=ok");}
''')
        for name in ('egl','gles','sdl'):run(['gcc','-shared','-fPIC',t/(name+'.c'),'-o',t/(name+'.so')])
        run(['gcc','-O2','-Wall','-Wextra',C/'graphics-probe.c','-o',t/'probe','-ldl'])
        env=dict(os.environ,CRUSTY_LIBEGL=str(t/'egl.so'),CRUSTY_LIBSDL=str(t/'sdl.so'),CRUSTY_LIBGLES=str(t/'gles.so'))
        r=run([t/'probe'],env=env)
        assert 'GL_RENDERER=FIXTURE_NO_GPU' in r.stdout and 'graphics_probe_status=0' in r.stdout
        r=subprocess.run([str(t/'probe')],env=dict(env,FIXTURE_FAIL_WINDOW='1'),text=True,capture_output=True,timeout=5)
        assert r.returncode==1 and 'SDL_CreateWindow: fixture deliberate window failure' in r.stderr and 'fixture_cleanup=ok' in r.stdout
        r=subprocess.run([str(t/'probe')],env=dict(env,CRUSTY_LIBEGL='/nonexistent/egl.so'),text=True,capture_output=True,timeout=5)
        assert r.returncode==1 and 'dlopen_EGL_error=' in r.stderr
        # Exercise native-run's boundary with a host shell fixture instead of ARM.
        g=t/'game';runtime=g/'crossmix/runtime/debian/lib/aarch64-linux-gnu';runtime.mkdir(parents=True)
        loader=runtime/'ld-linux-aarch64.so.1'
        loader.write_text('#!/bin/sh\nprintf "child_env=%s\\n" "$LD_LIBRARY_PATH"\nprintf "args=%s\\n" "$*"\n');loader.chmod(0o755)
        r=run(['sh',C/'native-run.sh','fixture'],env=dict(os.environ,GAMEDIR=str(g),MCPE_CARD_ROOT=str(t),MCPE_NATIVE_CHILD_LIBRARY_PATH='/firmware/helpers'))
        assert 'child_env=/firmware/helpers' in r.stdout and '--library-path' in r.stdout
        env=dict(os.environ,GAMEDIR=str(g),MCPE_CARD_ROOT=str(t));env.pop('MCPE_NATIVE_CHILD_LIBRARY_PATH',None)
        assert 'child_env=/nonexistent' in run(['sh',C/'native-run.sh','fixture'],env=env).stdout
    print('PASS EGL/GLES mock regression: GL4ES rejection, explicit EGL path, errors, cleanup, helper environment; no physical graphics')


if __name__=='__main__':main()
