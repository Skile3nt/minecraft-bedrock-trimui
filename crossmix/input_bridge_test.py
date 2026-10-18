#!/usr/bin/env python3
"""Real ELF interposition, failure injection and ARM64 ABI checks; no hardware."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

C = Path(__file__).resolve().parent
G = C.parent/'dist/stage/Data/ports/minecraftbedrock'


def run(args, **kwargs):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=15, **kwargs)
    assert p.returncode == 0, (args, p.stdout, p.stderr)
    return p.stdout


def main():
    with tempfile.TemporaryDirectory() as temp:
        p = Path(temp)
        (p/'fixture.c').write_text(r'''
#define _GNU_SOURCE
#include <linux/input.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
const char *udev_device_get_property_value(void*d,const char*k){errno=EAGAIN;return getenv("VALUE");}
const char *udev_device_get_devnode(void*d){return "/dev/input/event3";}
int open(const char*p,int flags,...){
 if(!strcmp(p,"/dev/input/event3"))return getenv("DENIED")?-1:99;
 int(*next)(const char*,int,...)=dlsym(RTLD_NEXT,"open");return next(p,flags,0600);
}
int close(int fd){if(fd==99)return 0;int(*next)(int)=dlsym(RTLD_NEXT,"close");return next(fd);}
int ioctl(int fd,unsigned long request,...){
 va_list a;va_start(a,request);void*v=va_arg(a,void*);va_end(a);
 unsigned n=_IOC_NR(request);
 if(n==0x06)strcpy(v,getenv("WRONG_NAME")?"keyboard":"TRIMUI Player1");
 else if(n==0x02){struct input_id*i=v;*i=(struct input_id){3,0x045e,0x028e,0x0114};if(getenv("WRONG_ID"))i->product=0;}
 else if(n==0x21){unsigned long*b=v;b[BTN_GAMEPAD/64]|=1UL<<(BTN_GAMEPAD%64);}
 else if(n==0x23){unsigned long*b=v;if(!getenv("NO_AXES"))b[0]=3;}
 return 0;
}
int libevdev_new_from_fd(int f,void**d){return -37;}
int libevdev_next_event(void*d,unsigned flags,struct input_event*e){*e=(struct input_event){.type=EV_KEY,.code=BTN_SOUTH,.value=1};return 0;}
''')
        (p/'check.c').write_text(r'''
#include <stdio.h>
#include <errno.h>
#include <linux/input.h>
const char *udev_device_get_property_value(void*,const char*);
int libevdev_new_from_fd(int,void**);
int libevdev_next_event(void*,unsigned,struct input_event*);
int main(){const char*v=udev_device_get_property_value(0,"ID_INPUT_JOYSTICK");
 printf("value=%s errno=%d\n",v?v:"missing",errno);
 void*d=0;printf("open=%d\n",libevdev_new_from_fd(2,&d));
 for(int i=0;i<200;i++){struct input_event e;int rc=libevdev_next_event(0,0,&e);if(rc || e.code!=BTN_SOUTH || e.value!=1)return 3;}
 return 0;}
''')
        (p/'versions.map').write_text('LIBUDEV_183 { global: udev_*; }; LIBEVDEV_1 { global: libevdev_*; };')
        for cc, arch in [('gcc', 'host'), ('aarch64-linux-gnu-gcc', 'arm64')]:
            run([cc, '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror', C/'input-bridge.c', '-ldl', '-o', p/(arch+'-bridge.so')])
            run([cc, '-shared', '-fPIC', p/'fixture.c', '-ldl', '-Wl,--version-script='+str(p/'versions.map'), '-o', p/(arch+'-fixture.so')])
            run([cc, p/'check.c', p/(arch+'-fixture.so'), '-Wl,-rpath,'+str(p), '-o', p/(arch+'-check')])
            for variables, value in [({}, '1'), ({'VALUE':'1'},'1'), ({'VALUE':'0'},'0'),
                    ({'DENIED':'1'},'missing'), ({'WRONG_NAME':'1'},'missing'),
                    ({'WRONG_ID':'1'},'missing'), ({'NO_AXES':'1'},'missing')]:
                logfile=p/'input.log';logfile.unlink(missing_ok=True)
                env=dict(os.environ, MCPE_INPUT_LOG=str(logfile), **variables)
                if arch=='host':
                    env['LD_PRELOAD']=str(p/(arch+'-bridge.so')); args=[p/(arch+'-check')]
                else:
                    d=G/'crossmix/runtime/debian'
                    args=['qemu-aarch64-static', d/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1',
                          '--library-path', str(d/'lib/aarch64-linux-gnu'),
                          '--preload', p/(arch+'-bridge.so'), p/(arch+'-check')]
                output=run(args, env=env)
                assert 'value='+value+' errno=11' in output, output
                assert 'open=-37' in output
                assert logfile.read_text().count('native_event')==96
        versions=run(['aarch64-linux-gnu-readelf','--version-info',p/'arm64-bridge.so'])
        assert all(tuple(map(int,v.split('.'))) <= (2,36) for v in re.findall(r'Name: GLIBC_([0-9.]+)',versions))
    print('PASS native gamepad discovery: conditional identity/capabilities fallback, explicit denial preserved, unchanged events/errors, bounded trace; host and ARM64 QEMU')


if __name__=='__main__': main()
