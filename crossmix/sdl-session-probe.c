/* GPL-3.0-or-later. Exercise the pinned Crusty SDL backend in the game session.
 * No Android runtime, APK, Minecraft library, settings or world data are read.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>

static int dimension(const char *s) {
    int v=0;while(*s>='0' && *s<='9'){v=v*10+(*s++-'0');if(v>4096)return -1;}
    return *s?-1:v;
}

static void *native(const char *name) {
    void **slot=dlsym(RTLD_DEFAULT,name);return slot?*slot:NULL;
}
int main(int argc,char **argv) {
    setvbuf(stdout,NULL,_IONBF,0);setvbuf(stderr,NULL,_IONBF,0);
    puts("sdl_session_probe=no Minecraft; pinned Crusty backend; GLES attributes unchanged");
    void (*init)(void)=dlsym(RTLD_DEFAULT,"init_backend");
    if(!init){fprintf(stderr,"probe_missing=init_backend\n");return 2;}
    puts("probe_stage=init_backend");init();
    void *(*context)(void)=native("__eglGetCurrentContext");
    void *(*display)(void)=native("__eglGetCurrentDisplay");
    void *(*surface)(int)=native("__eglGetCurrentSurface");
    void *ctx=context?context():NULL,*d=display?display():NULL,*s=surface?surface(0x3059):NULL;
    printf("probe_context=%p display=%p surface=%p\n",ctx,d,s);
    if(!ctx||!d||!s){puts("probe_status=1 (no native current context/surface)");return 1;}
    unsigned (*query)(void *,void *,int,int *)=native("__eglQuerySurface");
    int width=0,height=0;
    unsigned qw=query?query(d,s,0x3057,&width):0,qh=query?query(d,s,0x3056,&height):0;
    printf("native_EGL_surface=%dx%d width_ok=%u height_ok=%u\n",width,height,qw,qh);
    if(argc==4 && !strcmp(argv[1],"--size-check-only")) {
        int w=dimension(argv[2]),h=dimension(argv[3]);
        int rc=(!qw||!qh||w<=0||h<=0||width!=w||height!=h)?3:0;
        printf("size_gate requested=%dx%d result=%d (scaling to panel is not verified)\n",w,h,rc);
        return rc;
    }
    const unsigned char *(*get)(unsigned)=dlsym(RTLD_DEFAULT,"glGetString");
    void (*color)(float,float,float,float)=dlsym(RTLD_DEFAULT,"glClearColor");
    void (*clear)(unsigned)=dlsym(RTLD_DEFAULT,"glClear");
    unsigned (*error)(void)=dlsym(RTLD_DEFAULT,"glGetError");
    unsigned (*swap)(void *,void *)=native("__eglSwapBuffers");
    if(!get||!color||!clear||!error||!swap){puts("probe_status=2 (GLES symbols missing)");return 2;}
    const unsigned char *version=get(0x1f02),*renderer=get(0x1f01);
    printf("GL_VERSION=%s\nGL_RENDERER=%s\n",version?(const char *)version:"unavailable",renderer?(const char *)renderer:"unavailable");
    color(0.08f,0.25f,0.65f,1.f);clear(0x4000);
    unsigned code=error(),ok=swap(d,s);
    printf("GL_ERROR=0x%x swap_result=%u\n",code,ok);
    if(!ok){unsigned (*eglerror)(void)=native("__eglGetError");
        if(eglerror)printf("probe_swap_eglGetError=0x%x\n",eglerror());}
    if(ok)sleep(3);
    int rc=(!version||!renderer||code||!ok)?1:0;printf("probe_status=%d\n",rc);return rc;
}
