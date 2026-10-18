#!/usr/bin/env python3
"""Classifier equivalence/call counts and host microbenchmark; no GPU/FPS claim."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
from crusty_routing_test import ROOT, C, D, run


def main():
    evidence = []
    with tempfile.TemporaryDirectory(prefix='mcpe-backend-route-') as tmp:
        p = Path(tmp)
        (p/'old.c').write_bytes(subprocess.check_output(
            ['git', 'show', 'f77503e:crossmix/isolate-crusty.c'], cwd=ROOT))
        (p/'backend.c').write_text('int backend_data; int backend_function(void){return 7;}\n')
        (p/'fallback.c').write_text('int marker; int call_from_backend(void*p){return p==&marker;}\n')
        (p/'counter.c').write_text(r'''#define _GNU_SOURCE
#include <dlfcn.h>
unsigned long lookup_count;
int dladdr(const void*p,Dl_info*i){static int(*next)(const void*,Dl_info*);
if(!next)next=dlsym(RTLD_NEXT,"dladdr");lookup_count++;return next(p,i);}
''')
        (p/'check.c').write_text(r'''#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <assert.h>
int main(){
int(*classify)(void*)=dlsym(RTLD_DEFAULT,"call_from_backend");
void*(*load)(const char*,const char*)=dlsym(RTLD_DEFAULT,"load_lib_local");
unsigned long*count=dlsym(RTLD_DEFAULT,"lookup_count");
void*marker=dlsym(RTLD_DEFAULT,"marker");
assert(classify(main)==0 && classify(marker)==1 && classify((void*)1)==0);
void*h=load(NULL,"CRUSTY_LIBSDL");assert(h);
void*code=dlsym(h,"backend_function"),*data=dlsym(h,"backend_data");
assert(code && data && classify(code)==1 && classify(data)==1);
assert(classify(main)==0 && classify(marker)==1 && classify((void*)1)==0);
struct timespec start,end;*count=0;clock_gettime(CLOCK_MONOTONIC,&start);
unsigned sum=0;for(unsigned n=0;n<100000;n++)sum+=classify(code);
clock_gettime(CLOCK_MONOTONIC,&end);assert(sum==100000);
double ns=((end.tv_sec-start.tv_sec)*1e9+end.tv_nsec-start.tv_nsec)/100000;
unsigned long fast_lookups=*count;
/* A repeated registration must preserve results and use the fallback safely. */
assert(load(NULL,"CRUSTY_LIBSDL"));*count=0;
assert(classify(code)==1 && classify(data)==1 && classify(main)==0);
assert(*count>=2);
printf("{\"ns_per_call\":%.3f,\"dladdr_calls\":%lu,\"calls\":100000}\n",ns,fast_lookups);
}
''')
        for arch, cc in [('host', 'cc'), ('arm64', 'aarch64-linux-gnu-gcc')]:
            d = p/arch; d.mkdir()
            for name in ('backend', 'fallback', 'counter'):
                run([cc, '-O2', '-shared', '-fPIC', p/(name+'.c'), '-o', d/(name+'.so'), '-ldl'])
            run([cc, '-O2', p/'check.c', '-o', d/'check', '-ldl'])
            for version, source in [('old', p/'old.c'), ('new', C/'isolate-crusty.c')]:
                bridge=d/(version+'.so')
                run([cc, '-O2', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror', source, '-o', bridge, '-ldl'])
                session = d/version; session.mkdir()
                env=dict(os.environ, MCPE_SESSION_DIR=str(session), CRUSTY_LIBSDL=str(d/'backend.so'))
                preload=':'.join(str(f) for f in (bridge, d/'counter.so', d/'fallback.so'))
                env.pop('LD_PRELOAD', None)
                if arch == 'host':
                    args=[d/'check']; env['LD_PRELOAD']=preload
                else:
                    args=['qemu-aarch64-static', D/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1',
                          '--inhibit-cache', '--library-path', D/'lib/aarch64-linux-gnu', '--preload', preload, d/'check']
                samples=[json.loads(run(args, env=env).stdout) for _ in range(3)]
                assert all(s['dladdr_calls']==(100000 if version=='old' else 0) for s in samples), samples
                evidence.append({'arch':arch,'version':version,'calls':100000,
                    'dladdr_calls':samples[0]['dladdr_calls'],
                    'median_ns_per_call':statistics.median(s['ns_per_call'] for s in samples)})
    (ROOT/'dist/backend-route-results.json').write_text(json.dumps({
        'passed':True,'hardware_tested':False,'workload':'synthetic classifier only',
        'cases':evidence},indent=2)+'\n')
    print(json.dumps(evidence,indent=2))
    print('PASS backend routing equivalence, unknown/data/duplicate registration fallback, host + ARM64 QEMU; no GPU/FPS measurement')


if __name__ == '__main__':
    main()
