/* GPL-3.0-or-later. Read-only glibc binding audit; returns every address unchanged.
 * No libc dependencies or stdio in the dynamic linker's callbacks. The module
 * is selected using the PRIVATE loader's --audit, never inherited LD_AUDIT.
 */
#define _GNU_SOURCE
#include <link.h>
#include <stdint.h>
#include <stddef.h>

static char *append(char *out,char *end,const char *s) {
    if(!s)s="unknown";
    while(*s && out<end)*out++=*s++;
    return out;
}
static char *hex(char *out,char *end,uintptr_t value) {
    const char digits[]="0123456789abcdef";
    out=append(out,end,"0x");
    for(int n=(int)(sizeof(value)*2)-1;n>=0;n--)
        if(out<end)*out++=digits[(value>>(n*4))&15];
    return out;
}
static void emit(const char *buffer,size_t size) {
#if defined(__aarch64__)
    register long fd __asm__("x0")=2;
    register const char *text __asm__("x1")=buffer;
    register size_t count __asm__("x2")=size;
    register long number __asm__("x8")=64;
    __asm__ volatile("svc 0" : "+r"(fd) : "r"(text),"r"(count),"r"(number) : "memory");
#elif defined(__x86_64__)
    long result;
    __asm__ volatile("syscall" : "=a"(result) : "a"(1L),"D"(2L),"S"(buffer),"d"(size) : "rcx","r11","memory");
#else
#error Unsupported audit test architecture
#endif
}
static int prefix(const char *s,const char *p) {
    while(*p)if(*s++!=*p++)return 0;
    return 1;
}
unsigned la_version(unsigned version) { return version<LAV_CURRENT?version:LAV_CURRENT; }
unsigned la_objopen(struct link_map *map,Lmid_t ns,uintptr_t *cookie) {
    (void)ns;*cookie=(uintptr_t)map;
    char b[4096],*end=b+sizeof b-1,*p=append(b,end,"CrossMix audit_object=");
    p=append(p,end,map->l_name);*p++='\n';emit(b,(size_t)(p-b));
    return LA_FLG_BINDTO|LA_FLG_BINDFROM;
}
uintptr_t la_symbind64(Elf64_Sym *symbol,unsigned index,uintptr_t *from,uintptr_t *to,
                      unsigned *flags,const char *name) {
    (void)index;
    if(prefix(name,"egl") || prefix(name,"SDL_GL_") || prefix(name,"SDL_Init") ||
       prefix(name,"SDL_CreateWindow") || prefix(name,"SDL_Load") ||
       prefix(name,"dlopen")) {
        struct link_map *caller=(struct link_map *)*from,*provider=(struct link_map *)*to;
        char b[4096],*end=b+sizeof b-1,*p=append(b,end,"CrossMix binding symbol=");
        p=append(p,end,name);p=append(p,end," caller=");p=append(p,end,caller->l_name);
        p=append(p,end," provider=");p=append(p,end,provider->l_name);
        p=append(p,end," address=");p=hex(p,end,symbol->st_value);
        p=append(p,end,(*flags&LA_SYMB_DLSYM)?" lookup=dlsym":" lookup=relocation");
        *p++='\n';emit(b,(size_t)(p-b));
    }
    return symbol->st_value;
}
