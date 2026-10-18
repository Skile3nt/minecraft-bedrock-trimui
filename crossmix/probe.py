#!/usr/bin/env python3
"""Read-only discovery; a JSON report never claims a rendered frame."""
import argparse, ctypes, ctypes.util, json, os, platform, shlex, sys
from pathlib import Path


def libraries(native=False, trace=False):
    roots = [Path(os.environ.get('MCPE_CARD_ROOT', '/mnt/SDCARD')) / 'System/lib',
             Path('/usr/trimui/lib'), Path('/usr/lib'), Path('/lib')]
    result = {}
    for key, names in {'CRUSTY_LIBSDL': ['libSDL2-2.0.so.0', 'libSDL2.so'],
                       'CRUSTY_LIBEGL': ['libEGL.so.1', 'libEGL.so'],
                       'CRUSTY_LIBGLES': ['libGLESv2.so.2', 'libGLESv2.so']}.items():
        # CrossMix System/lib/libEGL.so.1 is a GL4ES wrapper, not native EGL.
        search_roots = roots[1:] + roots[:1] if native and key == 'CRUSTY_LIBEGL' else roots
        for root in search_roots:
            for name in names:
                p = root / name
                if trace and key == 'CRUSTY_LIBEGL':
                    print('native_EGL_candidate=' + str(p) + ' exists=' + str(p.is_file()), file=sys.stderr)
                if not p.is_file(): continue
                with p.open('rb') as f:
                    header = f.read(20)
                    # Reject the observed GL4ES EGL facade, including if copied
                    # under a firmware path. Do not confuse it with PowerVR.
                    gl4es = native and key == 'CRUSTY_LIBEGL' and b'gl4es_GetProcAddress' in f.read()
                if gl4es:
                    print("Rejected GL4ES EGL facade: " + str(p), file=sys.stderr)
                    continue
                if header[:5] == b'\x7fELF\x02' and int.from_bytes(header[18:20], 'little') == 183:
                    result[key] = str(p.resolve())
                    break
            if key in result: break
    return result


def inspect():
    libs = libraries()
    result = {'architecture': platform.machine(), 'libraries': libs,
              'nodes': {p: os.access(p, os.R_OK | os.W_OK) for p in
                        ['/dev/pvrsrvkm', '/dev/pvr_sync', '/dev/mali', '/dev/mali0', '/dev/fb0', '/dev/disp', '/dev/ion']},
              'expected_gpu': 'PowerVR GE8300 (Allwinner A133)',
              'validation': 'discovery only; no EGL context or game was started'}
    def read(path):
        try: return Path(path).read_text(errors='replace').replace('\0', ' ').strip()
        except OSError: return 'unavailable'
    result['model'] = read('/proc/device-tree/model')
    result['compatible'] = read('/proc/device-tree/compatible')
    result['memory'] = read('/proc/meminfo')
    result['alsa_cards'] = read('/proc/asound/cards')
    result['input_devices'] = read('/proc/bus/input/devices')
    try:
        libc = ctypes.CDLL(None)
        libc.gnu_get_libc_version.restype = ctypes.c_char_p
        result['system_glibc'] = libc.gnu_get_libc_version().decode()
    except (AttributeError, OSError): result['system_glibc'] = 'unknown'
    problems = []
    warnings = []
    if platform.machine() not in ('aarch64', 'arm64'): problems.append('ARM64 required')
    if len(libs) != 3: problems.append('Firmware ARM64 SDL2/EGL/GLES not found')
    if 'CRUSTY_LIBSDL' in libs:
        try:
            if 'CRUSTY_LIBGLES' in libs:
                ctypes.CDLL(libs['CRUSTY_LIBGLES'], mode=ctypes.RTLD_GLOBAL)
            sdl = ctypes.CDLL(libs['CRUSTY_LIBSDL'])
            sdl.SDL_GetVideoDriver.restype = ctypes.c_char_p
            result['sdl_video_drivers'] = [sdl.SDL_GetVideoDriver(i).decode()
                for i in range(sdl.SDL_GetNumVideoDrivers())]
            if 'mali' not in result['sdl_video_drivers']: problems.append('SDL2 mali driver missing')
        except (OSError, AttributeError) as e: problems.append('SDL2 load failed: ' + str(e))
    if not any(result['nodes'][p] for p in ('/dev/pvrsrvkm', '/dev/mali', '/dev/mali0')):
        # Real TrimUI logs show SDL mali and an accessible framebuffer while
        # these guessed node names are all absent/inaccessible. Node discovery
        # cannot establish EGL failure; leave that to graphics-probe.
        warnings.append('Known GPU node names not accessible; EGL/GLES test required')
    if not result['nodes']['/dev/fb0']: problems.append('Framebuffer unavailable')
    result['problems'] = problems
    result['warnings'] = warnings
    result['gpu_validated'] = False
    # Informational only: preserve the working launcher preflight. The GPU test
    # and future game session require these native paths explicitly.
    result['native_libraries'] = libraries(native=True)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path)
    p.add_argument('--libraries', action='store_true')
    p.add_argument('--native-libraries', action='store_true')
    args = p.parse_args()
    if args.libraries or args.native_libraries:
        libs = libraries(native=args.native_libraries, trace=args.native_libraries)
        if len(libs) != 3:
            print('Resolved libraries: ' + json.dumps(libs), file=sys.stderr)
            raise SystemExit('Firmware native SDL2/EGL/GLES discovery incomplete' if args.native_libraries else 'Firmware SDL2/EGL not found')
        for k, v in libs.items(): print(k + '=' + shlex.quote(v))
        return
    result = inspect()
    data = json.dumps(result, indent=2) + '\n'
    if args.output: args.output.write_text(data)
    print(data, end='')
    raise SystemExit(bool(result['problems']))


if __name__ == '__main__': main()
