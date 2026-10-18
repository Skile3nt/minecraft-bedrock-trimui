/* GPL-3.0-or-later. Bounded file-open observer; never changes assets or results.
 * Logs only particle JSON paths in this game's assets, never credentials.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>
static _Atomic unsigned count;
static void observe(const char *api,const char *path,int ok) {
    int saved=errno;
    /* Most opens are unrelated resources. Avoid environment/loader work on
     * that path, and stop touching the counter once the audit is complete. */
    if(!path || !strstr(path,"/particles/") || !strstr(path,".json"))return;
    unsigned used=atomic_load_explicit(&count,memory_order_relaxed);
    if(used>=256)return;
    const char *root=getenv("MCPE_PARTICLE_ROOT"),*log=getenv("MCPE_PARTICLE_LOG");
    if(!root || !log)return;
    if(strncmp(path,root,strlen(root)) || path[strlen(root)]!='/')return;
    do {
        if(used>=256)return;
    } while(!atomic_compare_exchange_weak_explicit(&count,&used,used+1,
                 memory_order_relaxed,memory_order_relaxed));
    char line[2048];
    int n=snprintf(line,sizeof line,"particle_asset_open api=%s ok=%d errno=%d path=%s\n",api,ok,ok?0:saved,path);
    if(n>0 && n<(int)sizeof line) {
        int fd=syscall(SYS_openat,AT_FDCWD,log,O_WRONLY|O_APPEND|O_CREAT|O_CLOEXEC,0600);
        if(fd>=0){syscall(SYS_write,fd,line,n);syscall(SYS_close,fd);}
    }
    errno=saved;
}
static int needs_mode(int flags) {
    return (flags&O_CREAT) || (flags&O_TMPFILE)==O_TMPFILE;
}
/* The host libc/interposer chain is fixed for this process. Publish resolved
 * functions safely when resource-loading threads first enter concurrently.
 * No pthread_once/loader lock is held while invoking the real open. */
#define RESOLVE(type,name) \
    static _Atomic(type) cached; \
    type next=atomic_load_explicit(&cached,memory_order_acquire); \
    if(!next){int saved=errno;next=(type)dlsym(RTLD_NEXT,#name); \
        if(next){atomic_store_explicit(&cached,next,memory_order_release);} errno=saved;}
#define OPEN_HOOK(name) \
int name(const char *path,int flags,...) { \
    mode_t mode=0; if(needs_mode(flags)){va_list ap;va_start(ap,flags);mode=va_arg(ap,int);va_end(ap);} \
    typedef int (*fn)(const char *,int,...); RESOLVE(fn,name) \
    int fd=next?next(path,flags,mode):(int)syscall(SYS_openat,AT_FDCWD,path,flags,mode); \
    observe(#name,path,fd>=0);return fd; \
}
OPEN_HOOK(open)
OPEN_HOOK(open64)
#define OPENAT_HOOK(name) \
int name(int dir,const char *path,int flags,...) { \
    mode_t mode=0; if(needs_mode(flags)){va_list ap;va_start(ap,flags);mode=va_arg(ap,int);va_end(ap);} \
    typedef int (*fn)(int,const char *,int,...); RESOLVE(fn,name) \
    int fd=next?next(dir,path,flags,mode):(int)syscall(SYS_openat,dir,path,flags,mode); \
    observe(#name,path,fd>=0);return fd; \
}
OPENAT_HOOK(openat)
OPENAT_HOOK(openat64)
#define FOPEN_HOOK(name) \
FILE *name(const char *path,const char *mode) { \
    typedef FILE *(*fn)(const char *,const char *); RESOLVE(fn,name) \
    if(!next){errno=ENOSYS;return NULL;} \
    FILE *f=next(path,mode);observe(#name,path,f!=NULL);return f; \
}
FOPEN_HOOK(fopen)
FOPEN_HOOK(fopen64)
