#!/usr/bin/env python3
"""Prepare Weston's conventional temporary socket directory, without deleting IPC.

The optional path argument is for isolated filesystem regression tests. Production
always uses /tmp/.X11-unix; existing directories and sockets are left untouched.
"""
import os
import stat
import sys
from pathlib import Path


def prepare(path=Path('/tmp/.X11-unix')):
    created = False
    try:
        os.mkdir(path, 0o1777)
        created = True
    except FileExistsError:
        pass
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode):
        raise RuntimeError('X11 socket path is not a real directory')
    if info.st_uid not in (0, os.geteuid()):
        raise RuntimeError('X11 socket directory has an unexpected owner')
    if created:
        # mkdir is subject to umask. Only change the directory we just created.
        os.chmod(path, 0o1777)
        info = os.lstat(path)
    if info.st_mode & stat.S_IWOTH and not info.st_mode & stat.S_ISVTX:
        raise RuntimeError('Existing public X11 socket directory lacks sticky bit')
    if not os.access(path, os.W_OK | os.X_OK):
        raise RuntimeError('X11 socket directory is not writable/searchable')
    print(f'x11_socket_directory={path} created={int(created)} mode={stat.S_IMODE(info.st_mode):04o}')


if __name__ == '__main__':
    try:
        prepare(Path(sys.argv[1]) if len(sys.argv) == 2 else Path('/tmp/.X11-unix'))
    except (OSError, RuntimeError) as error:
        print(f'X11 socket preparation failed: {error}', file=sys.stderr)
        sys.exit(1)
