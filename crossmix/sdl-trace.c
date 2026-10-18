/* GPL-3.0-or-later. Observe pinned Crusty call sites without replacing drivers.
 * Never wrap dlopen or caller-sensitive facade functions: preserve return PCs.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <link.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <errno.h>
#include <limits.h>
#include <stdatomic.h>
#include <time.h>
#include <unistd.h>

/* 225 batches of 240 swaps are about 30 minutes at the supported 30 Hz cap.
 * Keep the tmpfs trace bounded even if a game session is left running longer.
 * Tests may lower this compile-time limit; production builds use the default.
 */
#ifndef MCPE_FRAME_METRICS_MAX_BATCHES
#define MCPE_FRAME_METRICS_MAX_BATCHES 225
#endif

static void milestone(const char *event) {
    int saved=errno;
    const char *path=getenv("MCPE_TIMING_LOG");
    if(!path)return;
    FILE *f=fopen(path,"a");
    if(f) {
        struct timespec t;clock_gettime(CLOCK_BOOTTIME,&t);
        fprintf(f,"{\"uptime\":%ld.%03ld,\"event\":\"%s\"}\n",
                (long)t.tv_sec,t.tv_nsec/1000000,event);
        fclose(f);
    }
    errno=saved;
}

static void process_state(const char *step) {
    const char *root=getenv("MCPE_SESSION_DIR");
    const char *roles[]={"weston","xwayland"};
    if(!root)return;
    for(unsigned n=0;n<2;n++) {
        char path[4096];long pid=0;
        int len=snprintf(path,sizeof path,"%s/%s.pid",root,roles[n]);
        if(len<0 || (size_t)len>=sizeof path)continue;
        FILE *f=fopen(path,"r");
        if(f){char b[32];
            if(fgets(b,sizeof b,f)){unsigned j=0;
                while(b[j]>='0' && b[j]<='9') {
                    if(pid>(INT_MAX-(b[j]-'0'))/10){pid=0;break;}
                    pid=pid*10+(b[j++]-'0');
                }
                if(!j || (b[j]!='\n' && b[j]!='\0'))pid=0;
            }
            fclose(f);}
        int alive=pid>0?(kill((pid_t)pid,0)==0 || errno==EPERM):-1;
        fprintf(stderr,"CrossMix graphics_process_state step=%s role=%s pid=%ld alive=%d\n",step,roles[n],pid,alive);
    }
}

static void *native(const char *name) {
    void **slot=dlsym(RTLD_DEFAULT,name);
    return slot ? *slot : NULL;
}
static void origin(const char *name,void *f) {
    Dl_info i={0};
    if(f)dladdr(f,&i);
    fprintf(stderr,"CrossMix symbol=%s address=%p object=%s symbol_name=%s\n",
            name,f,i.dli_fname?i.dli_fname:"unknown",i.dli_sname?i.dli_sname:"unknown");
}
static int object(struct dl_phdr_info *i,size_t size,void *data) {
    (void)size;(void)data;
    fprintf(stderr,"CrossMix loaded_object=%s base=%p\n",i->dlpi_name,(void *)i->dlpi_addr);
    return 0;
}
static void error_snapshot(const char *step) {
    const char *(*error)(void)=native("__SDL_GetError");
    /* SDL has already constructed its error string. This is a terminal failure
     * snapshot, NOT the original EGL error (SDL may already have consumed it).
     */
    const char *message=error?error():NULL;
    fprintf(stderr,"CrossMix graphics_failure step=%s SDL_GetError=%s\n",step,message?message:"unavailable");
    unsigned (*eglerror)(void)=native("__eglGetError");
    if(eglerror)fprintf(stderr,"CrossMix terminal_eglGetError=0x%x (after SDL consumed error)\n",eglerror());
    dl_iterate_phdr(object,NULL);
}
int _SDL_Init(unsigned flags) {
    milestone("native_sdl_init_begin");
    int (*next)(unsigned)=dlsym(RTLD_NEXT,"_SDL_Init");
    fprintf(stderr,"CrossMix graphics_begin step=SDL_Init flags=0x%x\n",flags);
    const char *names[]={"__SDL_Init","__SDL_CreateWindow","__SDL_GL_CreateContext",
        "__eglGetDisplay","__eglInitialize","__eglChooseConfig","__eglCreateWindowSurface",
        "__eglCreateContext","__eglGetError"};
    for(unsigned n=0;n<sizeof names/sizeof names[0];n++)origin(names[n],native(names[n]));
    unsigned char version[3]={0};void (*getver)(void *)=native("__SDL_GetVersion");
    if(getver)getver(version);
    fprintf(stderr,"CrossMix native_SDL_version=%u.%u.%u\n",version[0],version[1],version[2]);
    int rc=next?next(flags):-1;
    milestone("native_sdl_init_end");
    const char *(*driver)(void)=native("__SDL_GetCurrentVideoDriver");
    const char *selected=driver?driver():NULL;
    fprintf(stderr,"CrossMix graphics_end step=SDL_Init result=%d driver=%s\n",rc,selected?selected:"none");
    if(rc)error_snapshot("SDL_Init");
    return rc;
}
void *_SDL_CreateWindow(const char *title,int x,int y,int width,int height,unsigned flags) {
    milestone("native_sdl_window_begin");
    void *(*next)(const char *,int,int,int,int,unsigned)=dlsym(RTLD_NEXT,"_SDL_CreateWindow");
    process_state("SDL_CreateWindow");
    fprintf(stderr,"CrossMix graphics_begin step=SDL_CreateWindow size=%dx%d flags=0x%x EGL_DRIVER=%s GL_DRIVER=%s\n",
            width,height,flags,getenv("SDL_VIDEO_EGL_DRIVER")?getenv("SDL_VIDEO_EGL_DRIVER"):"unset",
            getenv("SDL_VIDEO_GL_DRIVER")?getenv("SDL_VIDEO_GL_DRIVER"):"unset");
    /* Explicit loading is ONLY an A/B probe variant. The game path never sets
     * this switch; do not silently apply an unvalidated workaround to it.
     */
    if(getenv("MCPE_GRAPHICS_PROBE") && !strcmp(getenv("MCPE_GRAPHICS_PROBE"),"1") &&
       getenv("MCPE_SDL_PROBE_EXPLICIT_EGL") && !strcmp(getenv("MCPE_SDL_PROBE_EXPLICIT_EGL"),"1")) {
        void **slot=dlsym(RTLD_DEFAULT,"__SDL_CreateWindow");
        Dl_info i={0};if(slot && *slot)dladdr(*slot,&i);
        void *(*open)(const char *,int)=dlvsym(RTLD_NEXT,"dlopen","GLIBC_2.34");
        void *sdl=i.dli_fname&&open?open(i.dli_fname,RTLD_NOW|RTLD_NOLOAD):NULL;
        int (*load)(const char *)=sdl?dlsym(sdl,"SDL_GL_LoadLibrary"):NULL;
        const char *path=getenv("CRUSTY_LIBEGL");
        int rc=load&&path?load(path):-1;
        fprintf(stderr,"CrossMix probe_only SDL_GL_LoadLibrary explicit result=%d\n",rc);
        if(sdl)dlclose(sdl);
        if(rc)error_snapshot("SDL_GL_LoadLibrary");
    }
    void *w=next?next(title,x,y,width,height,flags):NULL;
    if(w)milestone("native_sdl_window_created");
    fprintf(stderr,"CrossMix graphics_end step=SDL_CreateWindow result=%p\n",w);
    if(!w)error_snapshot("SDL_CreateWindow");
    return w;
}
void *_SDL_GL_CreateContext(void *window) {
    milestone("native_sdl_context_begin");
    void *(*next)(void *)=dlsym(RTLD_NEXT,"_SDL_GL_CreateContext");
    process_state("SDL_GL_CreateContext");
    fprintf(stderr,"CrossMix graphics_begin step=SDL_GL_CreateContext window=%p\n",window);
    void *ctx=next?next(window):NULL;
    if(ctx)milestone("native_sdl_context_created");
    fprintf(stderr,"CrossMix graphics_end step=SDL_GL_CreateContext result=%p\n",ctx);
    if(!ctx)error_snapshot("SDL_GL_CreateContext");
    return ctx;
}
void _SDL_GL_SwapWindow(void *window) {
    static void (*next)(void *);
    static unsigned swaps;
    if(!next)next=dlsym(RTLD_NEXT,"_SDL_GL_SwapWindow");
    if(next)next(window);
    if(next && swaps++==0)milestone("first_sdl_swap_returned");
    /* Pinned Crusty swap_buffers -> this wrapper -> native SDL present.
     * Measure submitted-frame intervals, not physical scanout or gameplay FPS.
     * Bounded batches in RAM; no per-frame disk writes or GLES interception.
     */
    extern void crossmix_frame_batch(void *, void *);
    if(next)crossmix_frame_batch(window,__builtin_return_address(0));
}
static int compare_double(const void *a,const void *b) {
    double x=*(const double *)a,y=*(const double *)b;return (x>y)-(x<y);
}
void crossmix_frame_batch(void *window,void *caller) {
    static _Thread_local int checked,verified;
    static _Thread_local int metrics_disabled;
    static _Thread_local double previous,previous_boot,values[240],total;
    static _Thread_local unsigned count;
    static _Thread_local void (*getint)(unsigned,int *);
    static _Atomic unsigned completed_batches;
    if(metrics_disabled)return;
    const char *path=getenv("MCPE_BENCH_FILE");if(!path)return;
    if(!checked) {
        Dl_info info={0};dladdr(caller,&info);
        verified=info.dli_sname && !strcmp(info.dli_sname,"swap_buffers") &&
                 info.dli_fname && strstr(info.dli_fname,"libcrusty.so");
        checked=1;
    }
    if(!verified)return;
    struct timespec t,boot;
    if(clock_gettime(CLOCK_MONOTONIC,&t)||clock_gettime(CLOCK_BOOTTIME,&boot))return;
    double now=(double)t.tv_sec+t.tv_nsec/1e9;
    double uptime=(double)boot.tv_sec+boot.tv_nsec/1e9;
    if(previous>0){
        double active_delta=now-previous,boot_delta=uptime-previous_boot;
        if(boot_delta-active_delta>1.0){
            /* Do not combine two gameplay windows or count system suspend as
             * a single enormous frame. Awake stalls remain in the timings. */
            count=0;total=0;previous=now;previous_boot=uptime;return;
        }
        values[count++]=active_delta*1000;total+=active_delta;
    }
    previous=now;previous_boot=uptime;if(count!=240)return;
    unsigned batch=atomic_fetch_add_explicit(&completed_batches,1,memory_order_relaxed);
    if(batch>=MCPE_FRAME_METRICS_MAX_BATCHES){metrics_disabled=1;count=0;total=0;return;}
    if(batch+1>=MCPE_FRAME_METRICS_MAX_BATCHES)metrics_disabled=1;
    double sorted[240];memcpy(sorted,values,sizeof sorted);qsort(sorted,240,sizeof(double),compare_double);
    int viewport[4]={0},fbo=-1,sw=0,sh=0,dw=0,dh=0;
    if(!getint)getint=dlsym(RTLD_DEFAULT,"glGetIntegerv");
    if(getint){getint(0x0BA2,viewport);getint(0x8CA6,&fbo);}
    void *(*display)(void)=native("__eglGetCurrentDisplay");
    void *(*surface)(int)=native("__eglGetCurrentSurface");
    unsigned (*query)(void *,void *,int,int *)=native("__eglQuerySurface");
    if(display&&surface&&query){void*d=display(),*s=surface(0x3059);if(d&&s){query(d,s,0x3057,&sw);query(d,s,0x3056,&sh);}}
    void (*size)(void *,int *,int *)=native("__SDL_GL_GetDrawableSize");
    if(size)size(window,&dw,&dh);
    FILE *f=fopen(path,"a");
    if(f){fprintf(f,"{\"uptime\":%.3f,\"monotonic_seconds\":%.3f,\"clock_domain\":\"CLOCK_MONOTONIC; suspend excluded\",\"pid\":%d,\"metric\":\"verified_crusty_present_intervals\",\"intervals\":240,\"seconds\":%.6f,\"submission_rate\":%.3f,\"median_ms\":%.3f,\"p95_ms\":%.3f,\"p99_ms\":%.3f,\"max_ms\":%.3f,\"egl_surface\":[%d,%d],\"sdl_drawable\":[%d,%d],\"viewport\":[%d,%d,%d,%d],\"fbo\":%d}\n",
        uptime,now,(int)getpid(),total,240/total,(sorted[119]+sorted[120])/2,sorted[227],sorted[237],sorted[239],sw,sh,dw,dh,viewport[0],viewport[1],viewport[2],viewport[3],fbo);fclose(f);}
    count=0;total=0;
}
/* Pinned facade eglChooseConfig has NO caller check; forwarding through this
 * observer keeps its behavior. Other facade EGL functions DO check the caller
 * and must not be wrapped this way. This logs accidental facade use by SDL.
 */
unsigned eglChooseConfig(void *display,const int *attrs,void **configs,int size,int *count) {
    unsigned (*next)(void *,const int *,void **,int,int *)=dlsym(RTLD_NEXT,"eglChooseConfig");
    origin("facade_eglChooseConfig_caller",__builtin_return_address(0));
    unsigned rc=next?next(display,attrs,configs,size,count):0;
    fprintf(stderr,"CrossMix facade_eglChooseConfig result=%u count=%d\n",rc,rc&&count?*count:-1);
    return rc;
}
#define EGL_CALL(name,signature,args,failure) \
signature { \
    __typeof__(&name) next=dlsym(RTLD_NEXT,#name); \
    fprintf(stderr,"CrossMix graphics_begin step=%s\n",#name); \
    __typeof__(next args) result=next?next args:0; \
    fprintf(stderr,"CrossMix graphics_end step=%s success=%d\n",#name,!(failure)); \
    return result; \
}
EGL_CALL(_eglInitialize,unsigned _eglInitialize(void *d,int *major,int *minor),(d,major,minor),!result)
EGL_CALL(_eglCreateContext,void *_eglCreateContext(void *d,void *c,void *share,const int *a),(d,c,share,a),!result)
EGL_CALL(_eglCreateWindowSurface,void *_eglCreateWindowSurface(void *d,void *c,void *w,const int *a),(d,c,w,a),!result)
unsigned _eglGetError(void) {
    unsigned (*next)(void)=dlsym(RTLD_NEXT,"_eglGetError");
    unsigned code=next?next():0x3000;
    fprintf(stderr,"CrossMix forwarded_eglGetError=0x%x\n",code);
    return code;
}
