/* GPL-3.0-or-later. Scoped evdev discovery for CrossMix; no event injection.
 * The upstream EGLUT client requires udev's ID_INPUT_JOYSTICK property.
 * Firmware may expose evdev without a udev database. Only the positively
 * identified built-in TrimUI gamepad can receive that missing property.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/ioctl.h>

struct udev_device;
struct libevdev;
static void record(const char *format, ...) {
    int saved=errno;
    const char *path=getenv("MCPE_INPUT_LOG");
    if(path) {
        FILE *f=fopen(path,"a");
        if(f) {
            struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
            fprintf(f,"monotonic=%ld.%03ld ",(long)t.tv_sec,t.tv_nsec/1000000);
            va_list args;va_start(args,format);vfprintf(f,format,args);va_end(args);
            fputc('\n',f);fclose(f);
        }
    }
    errno=saved;
}
static int bit(const unsigned long *bits,unsigned n) {
    return !!(bits[n/(8*sizeof *bits)] & (1UL<<(n%(8*sizeof *bits))));
}
/* Exported for failure-injection tests; IDs alone are insufficient. */
int crossmix_is_builtin_pad(const char *name,const struct input_id *id,
                            const unsigned long *keys,const unsigned long *axes) {
    return name && !strcmp(name,"TRIMUI Player1") && id->bustype==BUS_USB &&
        id->vendor==0x045e && id->product==0x028e && id->version==0x0114 &&
        bit(keys,BTN_GAMEPAD) && bit(axes,ABS_X) && bit(axes,ABS_Y);
}
const char *udev_device_get_property_value(struct udev_device *dev,const char *key) {
    const char *(*next)(struct udev_device *,const char *)=
        dlsym(RTLD_NEXT,"udev_device_get_property_value");
    const char *value=next?next(dev,key):NULL;
    if(!key || strcmp(key,"ID_INPUT_JOYSTICK"))return value;
    int saved=errno;
    const char *(*nodefn)(struct udev_device *)=dlsym(RTLD_NEXT,"udev_device_get_devnode");
    const char *node=nodefn?nodefn(dev):NULL;
    if(!node || strncmp(node,"/dev/input/event",16))return value;
    char name[128]={0};struct input_id id={0};
    unsigned long keys[(KEY_CNT+8*sizeof(long)-1)/(8*sizeof(long))]={0};
    unsigned long axes[(ABS_CNT+8*sizeof(long)-1)/(8*sizeof(long))]={0};
    int fd=open(node,O_RDONLY|O_NONBLOCK|O_CLOEXEC),valid=0;
    if(fd>=0) {
        valid=ioctl(fd,EVIOCGNAME(sizeof name),name)>=0 &&
            ioctl(fd,EVIOCGID,&id)==0 &&
            ioctl(fd,EVIOCGBIT(EV_KEY,sizeof keys),keys)>=0 &&
            ioctl(fd,EVIOCGBIT(EV_ABS,sizeof axes),axes)>=0 &&
            crossmix_is_builtin_pad(name,&id,keys,axes);
        close(fd);
    }
    int fallback=!value && valid;
    record("discovery node=%s native_joystick=%s builtin_verified=%d fallback=%d",
           node,value?value:"missing",valid,fallback);
    errno=saved;
    return fallback?"1":value;
}
int libevdev_new_from_fd(int fd,struct libevdev **dev) {
    int (*next)(int,struct libevdev **)=dlsym(RTLD_NEXT,"libevdev_new_from_fd");
    int rc=next?next(fd,dev):-ENOSYS;
    record("native_gamepad_open fd=%d result=%d",fd,rc);
    return rc;
}
int libevdev_next_event(struct libevdev *dev,unsigned flags,struct input_event *event) {
    static int (*next)(struct libevdev *,unsigned,struct input_event *);
    static unsigned buttons,axes,triggers;
    if(!next)next=dlsym(RTLD_NEXT,"libevdev_next_event");
    int rc=next?next(dev,flags,event):-ENOSYS;
    /* Bounded, gamepad-only diagnostics. Never read keyboard/text/auth events. */
    if((rc==0 || rc==1) && event) {
        if(event->type==EV_KEY && event->code>=BTN_JOYSTICK && buttons++<96)
            record("native_event type=%u code=%u value=%d",event->type,event->code,event->value);
        else if(event->type==EV_ABS && (event->code==ABS_Z || event->code==ABS_RZ)) {
            if(triggers++<96)
                record("native_event type=%u code=%u value=%d",event->type,event->code,event->value);
        }
        else if(event->type==EV_ABS && axes++<96)
            record("native_event type=%u code=%u value=%d",event->type,event->code,event->value);
    }
    return rc;
}
