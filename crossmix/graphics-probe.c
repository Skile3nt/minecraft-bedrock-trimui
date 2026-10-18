/* GPL-3.0-or-later. Five-second SDL2/GLES2 test; no game or account data. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define LOAD(name, type) type name = (type)dlsym(sdl, #name); if (!name) { fprintf(stderr,"missing %s: %s\n",#name,dlerror()); return 1; }
typedef int (*init_fn)(unsigned);
typedef const char *(*error_fn)(void);
typedef int (*attr_fn)(int,int);
typedef int (*load_fn)(const char *);
typedef void *(*window_fn)(const char *,int,int,int,int,unsigned);
typedef void *(*context_fn)(void *);
typedef void (*window_void_fn)(void *);
typedef void (*delay_fn)(unsigned);
typedef void (*quit_fn)(void);
static void *open_library(const char *role, const char *path) {
    fprintf(stdout,"load_%s=%s\n",role,path?path:"unset");
    if(!path) return NULL;
    dlerror();
    void *handle=dlopen(path,RTLD_NOW|RTLD_GLOBAL);
    if(!handle) fprintf(stderr,"dlopen_%s_error=%s\n",role,dlerror());
    return handle;
}
int main(int argc,char **argv) {
    if(argc>1 && !strcmp(argv[1],"--help")) { puts("SDL2/GLES2 diagnostic; renders a green frame for five seconds on the device.");return 0; }
    setvbuf(stdout,NULL,_IONBF,0);setvbuf(stderr,NULL,_IONBF,0);
    puts("graphics_stage=load-libraries");
    const char *gles_path=getenv("CRUSTY_LIBGLES"),*sdl_path=getenv("CRUSTY_LIBSDL"),*egl_path=getenv("CRUSTY_LIBEGL");
    void *gles=open_library("GLES",gles_path);if(!gles)return 1;
    void *egl=open_library("EGL",egl_path);if(!egl)return 1;
    const char *required[]={"eglChooseConfig","eglGetDisplay","eglInitialize","eglCreateContext","eglGetError"};
    for(unsigned i=0;i<sizeof(required)/sizeof(required[0]);i++) {
        if(!dlsym(egl,required[i])) { fprintf(stderr,"EGL symbol missing: %s: %s\n",required[i],dlerror());return 1; }
    }
    void *sdl=open_library("SDL",sdl_path);if(!sdl)return 1;
    LOAD(SDL_Init,init_fn);LOAD(SDL_GetError,error_fn);LOAD(SDL_GL_SetAttribute,attr_fn);
    LOAD(SDL_GL_LoadLibrary,load_fn);LOAD(SDL_CreateWindow,window_fn);LOAD(SDL_GL_CreateContext,context_fn);
    LOAD(SDL_GL_SwapWindow,window_void_fn);LOAD(SDL_GL_DeleteContext,window_void_fn);
    LOAD(SDL_DestroyWindow,window_void_fn);LOAD(SDL_Delay,delay_fn);LOAD(SDL_Quit,quit_fn);
    puts("graphics_stage=SDL_Init");
    if(SDL_Init(0x20)) { fprintf(stderr,"SDL_Init: %s\n",SDL_GetError());return 1; }
    /* GLES2, RGB8, alpha8, depth16: avoid unnecessarily requiring depth24. */
    const int attrs[][2]={{21,4},{17,2},{18,0},{0,8},{1,8},{2,8},{3,8},{5,1},{6,16}};
    for(unsigned i=0;i<sizeof(attrs)/sizeof(attrs[0]);i++) {
        if(SDL_GL_SetAttribute(attrs[i][0],attrs[i][1])) { fprintf(stderr,"SDL_GL_SetAttribute(%d): %s\n",attrs[i][0],SDL_GetError());SDL_Quit();return 1; }
    }
    puts("graphics_stage=SDL_GL_LoadLibrary");
    if(SDL_GL_LoadLibrary(egl_path)) { fprintf(stderr,"SDL_GL_LoadLibrary: %s\n",SDL_GetError());SDL_Quit();return 1; }
    puts("graphics_stage=SDL_CreateWindow");
    void *window=SDL_CreateWindow("CrossMix GLES diagnostic",0,0,1280,720,3);
    if(!window) { fprintf(stderr,"SDL_CreateWindow: %s\n",SDL_GetError());SDL_Quit();return 1; }
    puts("graphics_stage=SDL_GL_CreateContext");
    void *context=SDL_GL_CreateContext(window);
    if(!context) { fprintf(stderr,"SDL_GL_CreateContext: %s\n",SDL_GetError());SDL_DestroyWindow(window);SDL_Quit();return 1; }
    const unsigned char *(*get_string)(unsigned)=dlsym(gles,"glGetString");
    void (*clear_color)(float,float,float,float)=dlsym(gles,"glClearColor");
    void (*clear)(unsigned)=dlsym(gles,"glClear");
    unsigned (*get_error)(void)=dlsym(gles,"glGetError");
    int status=0;
    if(get_string&&clear_color&&clear&&get_error) {
        const unsigned char *vendor=get_string(0x1f00),*renderer=get_string(0x1f01),*version=get_string(0x1f02),*extensions=get_string(0x1f03);
        printf("GL_VENDOR=%s\nGL_RENDERER=%s\nGL_VERSION=%s\nGL_EXTENSIONS=%s\n",vendor?vendor:(const unsigned char*)"unavailable",renderer?renderer:(const unsigned char*)"unavailable",version?version:(const unsigned char*)"unavailable",extensions?extensions:(const unsigned char*)"unavailable");
        puts("graphics_stage=swap-frame");
        clear_color(0.1f,0.55f,0.2f,1.0f);clear(0x4000);
        unsigned error=get_error();printf("GL_ERROR=0x%x\n",error);
        SDL_GL_SwapWindow(window);SDL_Delay(5000);
        if(!vendor||!renderer||!version||error)status=1;
    } else { fprintf(stderr,"GLES symbols missing\n");status=1; }
    SDL_GL_DeleteContext(context);SDL_DestroyWindow(window);SDL_Quit();
    printf("graphics_probe_status=%d\n",status);return status;
}
