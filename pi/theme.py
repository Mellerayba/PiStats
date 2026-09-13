"""
Mid-century-modern visual theme: palette, bundled font loading, and
hand-drawn geometric icons (weather + playback controls).

Icons are drawn with pygame primitives rather than Unicode/emoji glyphs
on purpose — it matches the clean-geometric aesthetic, and sidesteps
the font-glyph-availability problems hit earlier (tofu boxes for symbol
characters depending on what's installed on the Pi).

Design language: atomic-age restraint rather than postmodern clutter —
a starburst clock motif, pill-shaped hardware buttons, generous negative
space. Weather icons are drawn to fill a given rect (not a bare center
point) so every icon type — despite very different natural proportions
(a cloud is wider than a sun) — lines up identically against whatever
sits next to it.
"""
import math
import os

import pygame

# --- Palette: burnt orange / mustard / teal / walnut brown ---
# Deliberately saturated/deep rather than pale — pale tones wash out
# toward white on this panel's color reproduction.
CREAM = (192, 148, 94)
CREAM_DARK = (164, 122, 72)
BROWN = (60, 38, 30)
BROWN_SOFT = (94, 66, 54)
TERRACOTTA = (196, 90, 47)
RUST = (139, 58, 46)
MUSTARD = (224, 168, 46)
OLIVE = (98, 112, 64)
TEAL = (52, 108, 102)

_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "fonts", "SpaceGrotesk.ttf")

_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        f = pygame.font.Font(_FONT_PATH, size)
        f.set_bold(bold)
        _font_cache[key] = f
    return _font_cache[key]


def draw_text(surface, text, pos, size, color, bold=False, anchor="topleft"):
    """anchor: any pygame.Rect attribute name (topleft, midleft, center, ...)"""
    surf = font(size, bold).render(text, True, color)
    rect = surf.get_rect(**{anchor: pos})
    surface.blit(surf, rect)
    return rect


def draw_starburst(surface, center, inner_r, outer_r, spokes, color, width=1):
    """Atomic-age starburst motif — used behind the clock."""
    for i in range(spokes):
        angle = math.radians(i * (360 / spokes))
        x1 = center[0] + inner_r * math.cos(angle)
        y1 = center[1] + inner_r * math.sin(angle)
        x2 = center[0] + outer_r * math.cos(angle)
        y2 = center[1] + outer_r * math.sin(angle)
        pygame.draw.line(surface, color, (x1, y1), (x2, y2), width)


# --- Weather icons: each fits entirely within the given rect, so text
# placed at rect.right lines up consistently regardless of icon shape ---

def _draw_sun(surface, rect, color):
    cx, cy = rect.center
    r = min(rect.width, rect.height) * 0.28
    pygame.draw.circle(surface, color, (cx, cy), r)
    for i in range(8):
        angle = math.radians(i * 45)
        inner, outer = r + 2, min(rect.width, rect.height) * 0.5
        x1, y1 = cx + inner * math.cos(angle), cy + inner * math.sin(angle)
        x2, y2 = cx + outer * math.cos(angle), cy + outer * math.sin(angle)
        pygame.draw.line(surface, color, (x1, y1), (x2, y2), 2)


def _cloud_puffs(rect):
    r_main = rect.height * 0.3
    cy = rect.centery + rect.height * 0.08
    return [
        (rect.centerx, cy, r_main),
        (rect.centerx - rect.width * 0.2, cy + r_main * 0.3, r_main * 0.75),
        (rect.centerx + rect.width * 0.2, cy + r_main * 0.3, r_main * 0.75),
    ]


def _draw_cloud(surface, rect, color):
    for x, y, r in _cloud_puffs(rect):
        pygame.draw.circle(surface, color, (x, y), r)
    r_main = rect.height * 0.3
    cy = rect.centery + rect.height * 0.08
    pygame.draw.rect(surface, color,
                      (rect.centerx - rect.width * 0.3, cy, rect.width * 0.6, r_main * 0.6))


def _draw_rain(surface, rect, color, cloud_color):
    cloud_rect = pygame.Rect(rect.x, rect.y - rect.height * 0.15, rect.width, rect.height * 0.75)
    _draw_cloud(surface, cloud_rect, cloud_color)
    base_y = rect.bottom - rect.height * 0.15
    for i in range(3):
        x = rect.x + rect.width * 0.25 * (i + 1)
        pygame.draw.line(surface, color, (x, base_y), (x - 4, base_y + 8), 2)


def _draw_snow(surface, rect, color):
    cx, cy = rect.center
    size = min(rect.width, rect.height) * 0.4
    for angle_deg in (0, 60, 120):
        angle = math.radians(angle_deg)
        dx, dy = size * math.cos(angle), size * math.sin(angle)
        pygame.draw.line(surface, color, (cx - dx, cy - dy), (cx + dx, cy + dy), 2)


def _draw_lightning(surface, rect, color):
    cx, cy = rect.center
    s = min(rect.width, rect.height) * 0.45
    points = [
        (cx + s * 0.2, cy - s), (cx - s * 0.5, cy + s * 0.1), (cx, cy + s * 0.1),
        (cx - s * 0.2, cy + s), (cx + s * 0.5, cy - s * 0.15), (cx, cy - s * 0.15),
    ]
    pygame.draw.polygon(surface, color, points)


def _draw_fog(surface, rect, color):
    cx, cy = rect.center
    w = rect.width * 0.4
    for i, dy in enumerate((-6, 0, 6)):
        pygame.draw.line(surface, color, (cx - w, cy + dy), (cx + w, cy + dy), 2)


_WEATHER_ICONS = {
    0: "sun", 1: "sun",
    2: "cloud", 3: "cloud",
    45: "fog", 48: "fog",
    51: "rain", 53: "rain", 55: "rain", 56: "rain", 57: "rain",
    61: "rain", 63: "rain", 65: "rain", 66: "rain", 67: "rain",
    80: "rain", 81: "rain", 82: "rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow", 85: "snow", 86: "snow",
    95: "lightning", 96: "lightning", 99: "lightning",
}


def draw_weather_icon(surface, weather_code, rect, color=MUSTARD, cloud_color=BROWN_SOFT):
    """rect: a pygame.Rect the icon is drawn to fill (not overflow)."""
    kind = _WEATHER_ICONS.get(weather_code, "sun")
    if kind == "sun":
        _draw_sun(surface, rect, color)
    elif kind == "cloud":
        _draw_cloud(surface, rect, cloud_color)
    elif kind == "rain":
        _draw_rain(surface, rect, TEAL, cloud_color)
    elif kind == "snow":
        _draw_snow(surface, rect, color)
    elif kind == "lightning":
        _draw_lightning(surface, rect, RUST)
    elif kind == "fog":
        _draw_fog(surface, rect, cloud_color)


# --- Playback control icons ---

def _centroid(points):
    n = len(points)
    return sum(p[0] for p in points) / n, sum(p[1] for p in points) / n


def _recenter(points, center):
    """Shift points so their true centroid (not just bounding-box center)
    lands exactly on `center` — a play-triangle's geometric vertices
    average to a point well off from where it visually "looks" centered
    otherwise, which is why hand-eyeballed offsets kept drifting."""
    ox, oy = _centroid(points)
    return [(x - ox + center[0], y - oy + center[1]) for x, y in points]


def draw_play(surface, center, radius, color):
    """center/radius: the same values used for the badge ring behind it,
    so the icon is guaranteed to sit inside it correctly-sized."""
    s = radius * 0.9
    points = [(-s * 0.45, -s * 0.55), (-s * 0.45, s * 0.55), (s * 0.6, 0)]
    pygame.draw.polygon(surface, color, _recenter(points, center))


def draw_pause(surface, center, radius, color):
    bar_w = radius * 0.28
    bar_h = radius * 0.9
    gap = radius * 0.22
    cx, cy = center
    pygame.draw.rect(surface, color, (cx - gap - bar_w, cy - bar_h / 2, bar_w, bar_h), border_radius=2)
    pygame.draw.rect(surface, color, (cx + gap, cy - bar_h / 2, bar_w, bar_h), border_radius=2)


def _skip_icon(surface, center, radius, color, direction):
    """direction: +1 for skip-next (points right), -1 for skip-previous."""
    s = radius * 0.85
    tri = [(-s * 0.7, -s * 0.55), (-s * 0.7, s * 0.55), (s * 0.15, 0)]
    bar_x, bar_w, bar_h = s * 0.3, s * 0.28, s * 0.55
    bar_corners = [(bar_x, -bar_h), (bar_x + bar_w, -bar_h), (bar_x + bar_w, bar_h), (bar_x, bar_h)]
    if direction < 0:
        tri = [(-x, y) for x, y in tri]
        bar_corners = [(-x, y) for x, y in bar_corners]

    ox, oy = _centroid(tri + bar_corners)
    shift = (center[0] - ox, center[1] - oy)
    tri_final = [(x + shift[0], y + shift[1]) for x, y in tri]
    xs = [p[0] for p in bar_corners]
    ys = [p[1] for p in bar_corners]
    bar_rect = pygame.Rect(min(xs) + shift[0], min(ys) + shift[1], max(xs) - min(xs), max(ys) - min(ys))

    pygame.draw.polygon(surface, color, tri_final)
    pygame.draw.rect(surface, color, bar_rect, border_radius=2)


def draw_skip_next(surface, center, radius, color):
    _skip_icon(surface, center, radius, color, direction=1)


def draw_skip_prev(surface, center, radius, color):
    _skip_icon(surface, center, radius, color, direction=-1)
