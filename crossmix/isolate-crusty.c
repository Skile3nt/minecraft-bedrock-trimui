/* GPL-3.0-or-later. Scope the pinned Westonpack loader's two aliases. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <link.h>
#include <stdio.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* The pinned Crusty register_backend() keeps only the first /proc/self/maps
 * segment. A separate R-- header segment hides the executable SDL/EGL segment
 * from its dlopen caller check. Track the two actual dlopen objects instead;
 * keep Crusty's original classification for every other backend/caller.
 */
static void *backend_bases[2];
static int reported[2];

/* The checksum-pinned Crusty keeps both backend handles for process lifetime
 * (no dlclose import). Snapshot their executable segments at registration.
 * Positive lookups avoid dladdr's loader lock and symbol-table search on every
 * EGL call. Unknown addresses still use the original classification below.
 * A slot is immutable once published; an unexpected second registration
 * disables its fast path rather than rewriting memory read by other threads.
 */
#define BACKEND_CODE_RANGES 8
struct code_range { uintptr_t begin, end; };
static struct backend_code {
    struct code_range ranges[BACKEND_CODE_RANGES];
    unsigned count;
    _Atomic unsigned state; /* 0 empty, 1 capturing, 2 published, 3 disabled */
} backend_code[2];
struct code_snapshot { uintptr_t base; struct backend_code *code; unsigned count; };

static int snapshot_code(struct dl_phdr_info *info, size_t size, void *opaque) {
    (void)size;
    struct code_snapshot *s=opaque;
    if (info->dlpi_addr != s->base) return 0;
    for (unsigned n=0; n<info->dlpi_phnum; ++n) {
        const ElfW(Phdr) *p=&info->dlpi_phdr[n];
        if (p->p_type != PT_LOAD || !(p->p_flags & PF_X) || !p->p_memsz) continue;
        if (s->count == BACKEND_CODE_RANGES) { s->count=0; return 1; }
        uintptr_t begin=s->base+p->p_vaddr, end=begin+p->p_memsz;
        if (begin < s->base || end < begin) { s->count=0; return 1; }
        s->code->ranges[s->count++]=(struct code_range){begin,end};
    }
    return 1;
}

static void register_code(unsigned index, uintptr_t base) {
    struct backend_code *code=&backend_code[index];
    unsigned expected=0;
    if (!atomic_compare_exchange_strong_explicit(&code->state,&expected,1,
            memory_order_acq_rel,memory_order_acquire)) {
        atomic_store_explicit(&code->state,3,memory_order_release);
        return;
    }
    struct code_snapshot snapshot={base,code,0};
    dl_iterate_phdr(snapshot_code,&snapshot);
    code->count=snapshot.count;
    expected=1;
    atomic_compare_exchange_strong_explicit(&code->state,&expected,2,
            memory_order_release,memory_order_relaxed);
}

int _SDL_GL_SetAttribute(int attribute, int value) {
    int (*next)(int,int)=dlsym(RTLD_NEXT,"_SDL_GL_SetAttribute");
    fprintf(stderr,"CrossMix SDL_GL_attribute id=%d value=%d\n",attribute,value);
    return next ? next(attribute,value) : -1;
}

int call_from_backend(void *address) {
    static _Thread_local int (*next)(void *);
    if (!next) next=dlsym(RTLD_NEXT, "call_from_backend");
    int original = next ? next(address) : 0;
    if (original) return original;
    uintptr_t pc=(uintptr_t)address;
    for (unsigned i=0; i<2; ++i) {
        if (atomic_load_explicit(&backend_code[i].state,memory_order_acquire)!=2) continue;
        unsigned count=backend_code[i].count;
        for (unsigned n=0; n<count; ++n) {
            struct code_range r=backend_code[i].ranges[n];
            if (pc >= r.begin && pc < r.end) return 1;
        }
    }
    Dl_info info;
    if (dladdr(address, &info)) {
        for (unsigned i=0; i<2; ++i) {
            if (backend_bases[i] && info.dli_fbase == backend_bases[i]) {
                if (!original && !reported[i]) {
                    fprintf(stderr,"CrossMix backend_route_recovered role=%s caller=%s\n",
                            i ? "SDL" : "EGL", info.dli_fname);
                    reported[i]=1;
                }
                return 1;
            }
        }
    }
    return original;
}

/* Signature and PLT call sites verified in the checksum-pinned Crusty binary.
 * Interpose this exported helper instead of dlopen: Crusty's dlopen wrapper
 * classifies its caller by return address, which a general wrapper would hide.
 */
void *load_lib_local(const char *fallback, const char *key) {
    const char *session = getenv("MCPE_SESSION_DIR");
    if (!session || !key || (strcmp(key,"CRUSTY_LIBSDL") && strcmp(key,"CRUSTY_LIBEGL"))) {
        void *(*next)(const char *,const char *)=dlsym(RTLD_NEXT,"load_lib_local");
        return next ? next(fallback,key) : NULL;
    }
    const char *target=getenv(key);
    if (!target || !*target) target=fallback;
    char alias[4096];
    int n=snprintf(alias,sizeof alias,"%s/%s64.so",session,key);
    if (!target || n<0 || (size_t)n>=sizeof alias) { errno=ENAMETOOLONG; return NULL; }
    struct stat info;
    if (lstat(alias,&info) && symlink(target,alias)) {
        fprintf(stderr,"CrossMix: cannot create private %s alias: %s\n",key,strerror(errno));
        return NULL;
    }
    /* Explicit libc version skips Crusty's unversioned dlopen hook here only.
     * General application and SDL calls keep their original call sites.
     */
    void *(*real_dlopen)(const char *,int)=dlvsym(RTLD_NEXT,"dlopen","GLIBC_2.34");
    if (!real_dlopen) return NULL;
    void *handle=real_dlopen(alias,RTLD_NOW|RTLD_LOCAL);
    if (!handle) fprintf(stderr,"CrossMix: %s: %s\n",key,dlerror());
    if (handle) {
        struct link_map *map=NULL;
        if (!dlinfo(handle,RTLD_DI_LINKMAP,&map) && map) {
            unsigned index=!strcmp(key,"CRUSTY_LIBSDL");
            backend_bases[index]=(void *)map->l_addr;
            register_code(index,(uintptr_t)map->l_addr);
            fprintf(stderr,"CrossMix backend_registered role=%s path=%s base=%p\n",
                    index ? "SDL" : "EGL", map->l_name, backend_bases[index]);
        }
    }
    return handle;
}
