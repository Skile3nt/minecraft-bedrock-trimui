#!/usr/bin/env python3
"""Actual ELF observer, errno/IO/privacy/cap regression; host and ARM64 QEMU."""
import os
from pathlib import Path
import subprocess
import tempfile

C = Path(__file__).resolve().parent
D = C.parent/'dist/stage/Data/ports/minecraftbedrock/crossmix/runtime/debian'

def run(args, **kw):
    r = subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=15,**kw)
    assert r.returncode == 0, (r.stdout,r.stderr)
    return r.stdout

def main():
    with tempfile.TemporaryDirectory() as temp:
        t=Path(temp);root=t/'assets';p=root/'resource_packs/vanilla/particles/a.json'
        p.parent.mkdir(parents=True);p.write_text('{}')
        (t/'check.c').write_text(r'''
#define _GNU_SOURCE
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
int main(int n,char**a){
  for(int i=0;i<300;i++){
    int f=open(a[1],O_RDONLY);if(f<0)return 1;
    char b[2];if(read(f,b,2)!=2 || b[0]!='{')return 2;close(f);
  }
  FILE*f=fopen(a[1],"r");if(!f)return 3;fclose(f);
  errno=0; if(open(a[2],O_RDONLY)!=-1 || errno!=ENOENT)return 4;
  f=fopen(a[3],"w");if(!f)return 5;fputs("private",f);fclose(f);
  return 0;
}
''')
        for cc,arch in [('gcc','host'),('aarch64-linux-gnu-gcc','arm64')]:
            lib=t/(arch+'.so');check=t/(arch+'-check');log=t/(arch+'.log')
            run([cc,'-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',C/'particle-audit.c','-ldl','-o',lib])
            run([cc,t/'check.c','-o',check])
            env=dict(os.environ,MCPE_PARTICLE_ROOT=str(root),MCPE_PARTICLE_LOG=str(log))
            cmd=[check,p,p.with_name('missing.json'),t/'private-token.txt']
            if arch=='host':env['LD_PRELOAD']=str(lib)
            else:cmd=['qemu-aarch64-static',D/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1',
                     '--library-path',D/'lib/aarch64-linux-gnu','--preload',lib,*cmd]
            run(cmd,env=env)
            lines=log.read_text().splitlines()
            assert len(lines)==256 and all('ok=1' in x and str(p) in x for x in lines)
            assert 'private' not in log.read_text()
    print('PASS bounded particle IO observer: host + ARM64 QEMU; IO and errno preserved, private paths excluded')

if __name__=='__main__':main()
