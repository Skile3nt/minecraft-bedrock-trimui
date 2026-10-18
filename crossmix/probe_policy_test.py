#!/usr/bin/env python3
"""Regression from physical TrimUI discovery logs; mocked libraries, no graphics."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

C = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('probe', C/'probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def main():
    # Observed: aarch64, SDL mali, fb0 accessible, all guessed GPU nodes false.
    sdl = MagicMock()
    sdl.SDL_GetNumVideoDrivers.return_value = 1
    sdl.SDL_GetVideoDriver.return_value = b'mali'
    libc = MagicMock()
    libc.gnu_get_libc_version.return_value = b'2.33'
    libs = {'CRUSTY_LIBSDL': '/fixture/sdl', 'CRUSTY_LIBEGL': '/fixture/egl',
            'CRUSTY_LIBGLES': '/fixture/gles'}
    def load(path, **kwargs):
        return libc if path is None else sdl
    with patch.object(probe.platform, 'machine', return_value='aarch64'), \
         patch.object(probe, 'libraries', return_value=libs), \
         patch.object(probe.ctypes, 'CDLL', side_effect=load), \
         patch.object(probe.os, 'access', side_effect=lambda p, mode: p in ('/dev/fb0', '/dev/ion', '/dev/disp')):
        result = probe.inspect()
        assert not result['problems'], result
        assert result['warnings'] and not result['gpu_validated']
        sdl.SDL_GetVideoDriver.return_value = b'x11'
        assert 'SDL2 mali driver missing' in probe.inspect()['problems']
        sdl.SDL_GetVideoDriver.return_value = b'mali'
        with patch.object(probe, 'libraries', return_value={}):
            assert 'Firmware ARM64 SDL2/EGL/GLES not found' in probe.inspect()['problems']
    print('PASS captured TrimUI probe policy: unknown GPU nodes warn; missing firmware libraries/SDL driver still fail; graphics unverified')


if __name__ == '__main__': main()
