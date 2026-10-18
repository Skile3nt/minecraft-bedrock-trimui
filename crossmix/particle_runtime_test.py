#!/usr/bin/env python3
"""Differential file-hook operation counts and real /dev/null open microbenchmark.

Host timings are NOT TrimUI performance. QEMU checks ABI/semantics only.
"""
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
from particle_audit_test import C, D, run

COUNTER = r'''
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdatomic.h>
static _Atomic unsigned calls;
void *__real_dlsym(void *,const char *);
void *__wrap_dlsym(void *h,const char *n){atomic_fetch_add(&calls,1);return __real_dlsym(h,n);}
unsigned audit_lookup_count(void){return atomic_load(&calls);}
'''
CHECK = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
static const char *particle;
static void once(const char*p){
  int fd=open(p,O_RDONLY);assert(fd>=0);close(fd);
  fd=open64(p,O_RDONLY);assert(fd>=0);close(fd);
  fd=openat(AT_FDCWD,p,O_RDONLY);assert(fd>=0);close(fd);
  fd=openat64(AT_FDCWD,p,O_RDONLY);assert(fd>=0);close(fd);
  FILE*f=fopen(p,"r");assert(f);fclose(f);f=fopen64(p,"r");assert(f);fclose(f);
}
static void *worker(void*arg){(void)arg;for(int i=0;i<300;i++)once(particle);return NULL;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
int main(int argc,char**argv){
  assert(argc>=2);
  unsigned(*count)(void)=dlsym(RTLD_DEFAULT,"audit_lookup_count");assert(count);
  if(argc==2){
    double begin=now();for(int i=0;i<100000;i++){int fd=open("/dev/null",O_RDONLY);assert(fd>=0);close(fd);}
    double elapsed=now()-begin;printf("{\"opens\":100000,\"lookup_calls\":%u,\"ns_per_open_close\":%.2f}\n",count(),elapsed*1e9/100000);return 0;
  }
  particle=argv[1];pthread_t threads[4];
  for(int i=0;i<4;i++)assert(!pthread_create(&threads[i],NULL,worker,NULL));
  for(int i=0;i<4;i++)assert(!pthread_join(threads[i],NULL));
  unsigned warm=count();assert(warm>=6 && warm<=24);
  once(particle);once("/dev/null");assert(count()==warm);
  errno=0;assert(open(argv[2],O_RDONLY)==-1 && errno==ENOENT);
  errno=0;assert(open64(argv[2],O_RDONLY)==-1 && errno==ENOENT);
  errno=0;assert(openat(AT_FDCWD,argv[2],O_RDONLY)==-1 && errno==ENOENT);
  errno=0;assert(openat64(AT_FDCWD,argv[2],O_RDONLY)==-1 && errno==ENOENT);
  errno=0;assert(!fopen(argv[2],"r") && errno==ENOENT);
  errno=0;assert(!fopen64(argv[2],"r") && errno==ENOENT);
  umask(0);int fd=open(argv[3],O_CREAT|O_EXCL|O_WRONLY,0600);assert(fd>=0);
  struct stat st;assert(!fstat(fd,&st) && (st.st_mode&0777)==0600);
  assert(write(fd,"ok",2)==2);close(fd);
  errno=0;assert(open(argv[3],O_CREAT|O_EXCL|O_WRONLY,0644)==-1 && errno==EEXIST);
  assert(count()==warm);printf("{\"threaded_lookups\":%u,\"passed\":true}\n",warm);return 0;
}
'''


def main():
    results = {'hardware_tested': False, 'timing_scope': 'host actual open/close /dev/null; no GPU/game', 'checks': [], 'host_runs': {}}
    with tempfile.TemporaryDirectory(prefix='mcpe-file-hooks-') as tmp:
        p=Path(tmp); (p/'counter.c').write_text(COUNTER); (p/'check.c').write_text(CHECK)
        (p/'old.c').write_bytes(subprocess.check_output(['git','show','f77503e:crossmix/particle-audit.c'],cwd=C.parent))
        asset=p/'assets/resource_packs/vanilla/particles/a.json';asset.parent.mkdir(parents=True);asset.write_text('{}')
        for cc,arch in [('gcc','host'),('aarch64-linux-gnu-gcc','arm64')]:
            for version,source in [('before',p/'old.c'),('after',C/'particle-audit.c')]:
                lib=p/f'{arch}-{version}.so'
                run([cc,'-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',source,p/'counter.c','-Wl,--wrap=dlsym','-ldl','-o',lib])
            check=p/f'{arch}-check';run([cc,'-O2','-Wall','-Wextra','-Werror',p/'check.c','-pthread','-ldl','-o',check])
            def call(version, *args):
                env=dict(os.environ,MCPE_PARTICLE_ROOT=str(p/'assets'),MCPE_PARTICLE_LOG=str(p/f'{arch}.log'))
                env.pop('LD_PRELOAD',None)
                lib=p/f'{arch}-{version}.so'; cmd=[check,*args]
                if arch=='host': env['LD_PRELOAD']=str(lib)
                else: cmd=['qemu-aarch64-static',D/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1','--library-path',D/'lib/aarch64-linux-gnu','--preload',lib,*cmd]
                return json.loads(run(cmd,env=env))
            results['checks'].append({'arch':arch,**call('after',asset,p/'missing',p/f'{arch}-created')})
            lines=(p/f'{arch}.log').read_text().splitlines()
            assert len(lines)==256 and all(str(asset) in line for line in lines)
            if arch=='host':
                samples={'before':[],'after':[]}
                for rep in range(7):
                    for version in (('before','after') if rep%2==0 else ('after','before')):
                        row=call(version,'bench');samples[version].append(row)
                        assert row['lookup_calls']==(100000 if version=='before' else 1)
                results['host_runs']=samples
                results['host_median_ns']={k:statistics.median(v['ns_per_open_close'] for v in rows) for k,rows in samples.items()}
    out=C.parent/'dist/particle-runtime-results.json';out.write_text(json.dumps(results,indent=2)+'\n')
    print('PASS six APIs + concurrent reads + errno/mode/privacy/cap: host and ARM64 QEMU')
    print('Host /dev/null medians (ns/open+close):',results['host_median_ns'])
    print('Loader lookups / 100000 opens: 100000 -> 1; not a gameplay/FPS benchmark')

if __name__=='__main__':main()
