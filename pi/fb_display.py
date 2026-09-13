"""
Shared framebuffer helper for the piscreen panel.

This OS's SDL2 (from apt's python3-pygame) has no "fbdev" driver
compiled in, and KMSDRM doesn't apply since fbtft-style panels like
piscreen expose a legacy /dev/fbN device, not a DRM one. So instead of
pygame.display, we render to an off-screen pygame.Surface and write
raw RGB565 bytes into the framebuffer via mmap. See pi/hello_world.py
for the original de-risking script this was extracted from.

Which /dev/fbN number the panel gets depends on driver init order at
boot (e.g. whether an HDMI display/capture card is also connected), so
it isn't stable across reboots — it showed up as fb1 in earlier testing
and fb0 once nothing else claimed fb0 first. We auto-detect it instead
of hardcoding a number, by finding the /sys/class/graphics/fbN whose
driver name starts with "fb_" (the fbtft naming convention for these
SPI panel drivers, e.g. "fb_ili9486") rather than "simple" (HDMI).
"""
import glob
import mmap
import os

import numpy as np
import pygame


def _find_panel_fb():
    for path in sorted(glob.glob("/sys/class/graphics/fb*")):
        name_file = os.path.join(path, "name")
        if not os.path.isfile(name_file):
            continue
        with open(name_file) as f:
            name = f.read().strip()
        if name.startswith("fb_"):
            return os.path.basename(path)
    raise RuntimeError(
        "No fbtft-style framebuffer (name starting 'fb_') found under "
        "/sys/class/graphics/ — is the piscreen overlay loaded?"
    )


class Framebuffer:
    def __init__(self, path=None, fb_name=None):
        fb_name = fb_name or _find_panel_fb()
        path = path or f"/dev/{fb_name}"
        base = f"/sys/class/graphics/{fb_name}"
        with open(f"{base}/virtual_size") as f:
            self.width, self.height = (int(x) for x in f.read().strip().split(","))
        with open(f"{base}/bits_per_pixel") as f:
            bpp = int(f.read().strip())
        if bpp != 16:
            raise RuntimeError(f"expected 16bpp (RGB565) framebuffer, got {bpp}bpp")

        self._fd = os.open(path, os.O_RDWR)
        size = self.width * self.height * 2
        self._mmap = mmap.mmap(
            self._fd, size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ
        )

    def blit(self, surface):
        # pygame's array3d is indexed [x, y, channel]; framebuffer memory
        # is row-major [y, x], so transpose before packing.
        arr = pygame.surfarray.array3d(surface).transpose(1, 0, 2).astype(np.uint16)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        pixels = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        self._mmap.seek(0)
        self._mmap.write(pixels.astype("<u2").tobytes())

    def close(self):
        self._mmap.close()
        os.close(self._fd)
