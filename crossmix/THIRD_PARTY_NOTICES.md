# Private runtime provenance

The Minecraft launcher and its licenses are retained from Standard v2.0.1.
Exact upstream source archive, integration patch and isolation shim source
are included under crossmix/source and crossmix/isolate-crusty.c.

Debian packages are unmodified official ARM64 bookworm binaries extracted
locally. Version, URL path, size and SHA-256 are recorded in debian-lock.json.
libjpeg-turbo8 is an Ubuntu Jammy ARM64 package with its official URL and checksum
in the same lock. Its source is available at https://launchpad.net/ubuntu/+source/libjpeg-turbo/2.1.2-0ubuntu1.
Their copyright/license texts are in runtime/debian/usr/share/doc/*/copyright.
Corresponding Debian sources are available through https://sources.debian.org/
using the exact versions in the lock (glibc, gcc-12, libevdev, alsa-lib,
zlib, wayland, bash and ncurses). No packages are installed in the firmware root.

Westonpack 0.2 is retained from the exact PortMaster checksum pinned upstream.
https://github.com/binarycounter/Westonpack/wiki
https://github.com/PortsMaster/PortMaster-New/tree/main/runtimes
This input has patched Weston and Crusty binaries but no complete bundled
license/source tree. This build is a local experimental package; before public
redistribution the corresponding modified Weston/Crusty sources and full
component notices must be obtained from the runtime distributor. The MIT license
of the Westonpack repository alone does not cover all bundled components.

The firmware's PowerVR driver, SDL2, LOVE and Python are referenced in place.
No proprietary Minecraft or proprietary GPU files are included in this package.
