"""
Direct-framebuffer hello-world for the piscreen panel (/dev/fb1).

Confirms pygame can render to the actual framebuffer device (not just
console text), and that frame-by-frame updates work, before building
the real UI. See fb_display.py for why this bypasses pygame.display
entirely. Ctrl+C to quit.

Requires numpy: sudo apt install -y python3-numpy

Run on the Pi with:
    python3 hello_world.py
"""
import sys
import time

import pygame

from fb_display import Framebuffer

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 30, 30)


def main():
    pygame.init()
    fb = Framebuffer()
    print(f"Framebuffer: {fb.width}x{fb.height}")

    surface = pygame.Surface((fb.width, fb.height))
    font_big = pygame.font.SysFont(None, 48)
    font_small = pygame.font.SysFont(None, 28)
    clock = pygame.time.Clock()
    frame = 0

    try:
        while True:
            surface.fill(WHITE)

            title = font_big.render("Hello, Pi!", True, BLACK)
            surface.blit(title, (20, 20))

            now_str = time.strftime("%H:%M:%S")
            clock_surf = font_small.render(now_str, True, BLACK)
            surface.blit(clock_surf, (20, 80))

            # Bouncing box so it's obvious frames are actually updating,
            # not just a static image left over on the framebuffer.
            box_x = 20 + (frame * 4) % max(fb.width - 60, 1)
            pygame.draw.rect(surface, RED, (box_x, 130, 40, 40))

            fb.blit(surface)
            frame += 1
            clock.tick(15)
    finally:
        fb.close()
        pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
