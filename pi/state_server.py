"""
Pi-side socket server: accepts a connection from the Mac, receives its
pushed state (battery, now-playing + artwork, system stats, weather) as
newline-delimited JSON, and renders it to the piscreen panel using the
Pi's own system clock for the time/date display.

Touch (previous/play-pause/next, via the XPT2046 touchscreen) sends
playback commands back to the Mac over the same connection.

Visual design: a mid-century-modern theme (terracotta/mustard/teal/
walnut brown, starburst clock motif, pill-shaped hardware buttons) —
see theme.py for the palette, bundled font, and hand-drawn geometric
icons (deliberately not Unicode/emoji glyphs, both for the aesthetic
and because font glyph coverage on the Pi proved unreliable earlier).

Requires: sudo apt install -y python3-evdev

Run on the Pi with:
    python3 state_server.py
"""
import base64
import io
import json
import math
import socket
import threading
import time

import pygame

import theme
from fb_display import Framebuffer
from touch_input import start_touch_listener

HOST = "0.0.0.0"
PORT = 8765

_state_lock = threading.Lock()
_state = {}

_client_lock = threading.Lock()
_client_conn = None

_flash_lock = threading.Lock()
_button_flash = {}  # command -> time.time() when last tapped

FLASH_DURATION = 0.25

# (x, y, w, h, command) — command matches mac/state_source.py's
# _COMMAND_MAP keys. Icons/labels are drawn dynamically in the render
# loop so the play/pause icon can reflect actual playback state.
_BUTTONS = [
    (30, 222, 130, 56, "previous"),
    (175, 222, 130, 56, "toggle"),
    (320, 222, 130, 56, "next"),
]


def send_command(command):
    """Send a playback command back to the Mac (called from _handle_tap)."""
    with _client_lock:
        conn = _client_conn
    if conn is None:
        return
    try:
        conn.sendall((json.dumps({"type": "command", "command": command}) + "\n").encode())
    except OSError:
        pass


def _handle_client(conn, addr):
    global _client_conn
    print(f"Mac connected from {addr}")
    with _client_lock:
        _client_conn = conn
    buf = b""
    try:
        with conn:
            while True:
                try:
                    chunk = conn.recv(4096)
                except OSError:
                    # e.g. ConnectionResetError when the Mac's end dies
                    # abruptly (sleep/wake, network drop) instead of
                    # closing cleanly. Treat it the same as a normal
                    # disconnect rather than letting it propagate and
                    # kill _server_loop's whole accept loop, which would
                    # make the Pi refuse every future connection.
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    with _state_lock:
                        _state.update(msg)
    finally:
        print("Mac disconnected")
        with _client_lock:
            if _client_conn is conn:
                _client_conn = None


def _server_loop():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(1)
        print(f"Listening on {HOST}:{PORT}")
        while True:
            conn, addr = srv.accept()
            try:
                _handle_client(conn, addr)  # one Mac at a time is fine
            except Exception as e:
                # Whatever went wrong with this connection, the accept
                # loop must survive it — this is the only thing standing
                # between a bad connection and the Pi refusing every
                # future one until someone notices and restarts it.
                print(f"_handle_client crashed: {e}")


def _draw_header(surface, w, s):
    pygame.draw.rect(surface, theme.BROWN, (0, 0, w, 54))

    # three zones: weather (left) | clock+date (center) | battery (right)
    wx = s.get("weather") or {}
    if wx.get("temp_c") is not None:
        icon_rect = pygame.Rect(16, 10, 34, 34)
        theme.draw_weather_icon(surface, wx.get("weather_code"), icon_rect)
        theme.draw_text(surface, f"{round(wx['temp_c'])}°", (icon_rect.right + 8, icon_rect.centery),
                         18, theme.MUSTARD, bold=True, anchor="midleft")

    # atomic-age starburst behind the clock — quintessential mid-century
    # motif, and it's literally a clock, so it earns its place
    theme.draw_starburst(surface, (w // 2, 27), 15, 24, 16, theme.BROWN_SOFT, width=2)

    now = time.localtime()
    sep = ":" if int(time.time()) % 2 == 0 else " "
    clock_text = time.strftime(f"%H{sep}%M", now)
    theme.draw_text(surface, clock_text, (w // 2, 19), 34, theme.CREAM, bold=True, anchor="center")
    theme.draw_text(surface, time.strftime("%a %d %b", now), (w // 2, 43), 13, theme.MUSTARD, anchor="center")

    batt = s.get("battery") or {}
    percent = batt.get("percent")
    charging = bool(batt.get("charging"))
    pill_color = theme.TERRACOTTA if charging else theme.MUSTARD
    pill_rect = pygame.Rect(w - 76, 10, 60, 34)
    pygame.draw.rect(surface, pill_color, pill_rect, border_radius=17)
    percent_text = f"{percent}%" if percent is not None else "?%"
    theme.draw_text(surface, percent_text, pill_rect.center, 16, theme.BROWN, bold=True, anchor="center")

    pygame.draw.rect(surface, theme.TERRACOTTA, (0, 54, w, 3))


def _draw_art_placeholder(surface, rect):
    pygame.draw.rect(surface, theme.CREAM_DARK, rect)
    cx, cy = rect.center
    pygame.draw.circle(surface, theme.OLIVE, (cx, cy), 34, 2)
    pygame.draw.circle(surface, theme.TERRACOTTA, (cx, cy), 20, 2)
    pygame.draw.circle(surface, theme.BROWN, (cx, cy), 5)


def _draw_now_playing(surface, w, s, artwork_cache, t):
    np_ = s.get("now_playing") or {}
    art_rect = pygame.Rect(16, 64, 130, 130)

    artwork_b64 = np_.get("artwork_b64")
    if artwork_b64 and artwork_b64 != artwork_cache["b64"]:
        try:
            raw = base64.b64decode(artwork_b64)
            img = pygame.image.load(io.BytesIO(raw))
            img = pygame.transform.smoothscale(img, (art_rect.width, art_rect.height))
            artwork_cache["b64"] = artwork_b64
            artwork_cache["surf"] = img
        except Exception as e:
            print("artwork decode failed:", e)
    elif not artwork_b64:
        artwork_cache["b64"] = None
        artwork_cache["surf"] = None

    if artwork_cache["surf"]:
        surface.blit(artwork_cache["surf"], art_rect)
    else:
        _draw_art_placeholder(surface, art_rect)
    pygame.draw.rect(surface, theme.TERRACOTTA, art_rect, 4, border_radius=6)
    # corner "sticker" accent
    corner = [
        (art_rect.right - 24, art_rect.top),
        (art_rect.right, art_rect.top),
        (art_rect.right, art_rect.top + 24),
    ]
    pygame.draw.polygon(surface, theme.MUSTARD, corner)

    text_x = art_rect.right + 16
    is_playing = bool(np_.get("playing"))
    title = (np_.get("title") or "Nothing playing")[:22]
    artist = (np_.get("artist") or "")[:26]
    album = (np_.get("album") or "")[:26]
    theme.draw_text(surface, title, (text_x, art_rect.top), 21, theme.BROWN, bold=True)
    theme.draw_text(surface, artist, (text_x, art_rect.top + 28), 16, theme.TERRACOTTA)
    theme.draw_text(surface, album, (text_x, art_rect.top + 50), 13, theme.OLIVE)

    # equalizer bars: bounce when playing, static short bars when not
    bar_base_y = art_rect.top + 100
    for i in range(4):
        bx = text_x + i * 10
        if is_playing:
            phase = t * 5 + i * 1.7
            bar_h = 6 + (math.sin(phase) * 0.5 + 0.5) * 18
            color = theme.TERRACOTTA
        else:
            bar_h = 5
            color = theme.CREAM_DARK
        pygame.draw.rect(surface, color, (bx, bar_base_y - bar_h, 6, bar_h), border_radius=2)

    # progress bar (extrapolated between the Mac's once-a-second pushes)
    elapsed = np_.get("elapsed_s") or 0.0
    duration = np_.get("duration_s") or 0.0
    updated_epoch = np_.get("updated_epoch") or 0.0
    if is_playing and updated_epoch:
        elapsed += max(0.0, time.time() - updated_epoch)

    bar_rect = pygame.Rect(16, 200, w - 32, 10)
    pygame.draw.rect(surface, theme.CREAM_DARK, bar_rect, border_radius=5)
    if duration:
        frac = max(0.0, min(1.0, elapsed / duration))
        fill_w = max(10, int(bar_rect.width * frac))
        pygame.draw.rect(surface, theme.TERRACOTTA, (bar_rect.x, bar_rect.y, fill_w, bar_rect.height), border_radius=5)
        scrubber_x = bar_rect.x + int(bar_rect.width * frac)
        pygame.draw.circle(surface, theme.BROWN, (scrubber_x, bar_rect.centery), 7)

    return is_playing


def _draw_buttons(surface, is_playing, t):
    with _flash_lock:
        flashes = dict(_button_flash)

    for x, y, w, h, command in _BUTTONS:
        rect = pygame.Rect(x, y, w, h)
        radius = rect.height // 2
        flash_at = flashes.get(command, 0)
        flashing = (t - flash_at) < FLASH_DURATION

        base = theme.ORANGE_BRIGHT if command == "toggle" else theme.TERRACOTTA

        # chunky raised-button look: a darker shadow layer offset below,
        # the real face on top, flashing bright on tap
        shadow_rect = rect.move(0, 4)
        pygame.draw.rect(surface, theme.RUST, shadow_rect, border_radius=radius)
        fill = theme.CREAM if flashing else base
        pygame.draw.rect(surface, fill, rect, border_radius=radius)
        pygame.draw.rect(surface, theme.BROWN, rect, width=2, border_radius=radius)

        # subtle badge ring behind the icon — old radio/dashboard dial feel.
        # Icons are drawn using this exact same center/radius so they're
        # guaranteed to land inside it correctly, instead of being sized
        # off the button rect and drifting out of alignment with the ring.
        icon_color = theme.BROWN if flashing else theme.CREAM
        badge_r = min(rect.width, rect.height) * 0.34
        pygame.draw.circle(surface, icon_color, rect.center, int(badge_r), 1)

        if command == "previous":
            theme.draw_skip_prev(surface, rect.center, badge_r, icon_color)
        elif command == "next":
            theme.draw_skip_next(surface, rect.center, badge_r, icon_color)
        elif command == "toggle":
            if is_playing:
                theme.draw_pause(surface, rect.center, badge_r, icon_color)
            else:
                theme.draw_play(surface, rect.center, badge_r, icon_color)


def _draw_meter(surface, x, width, y, label, value, bar_color):
    value = value if value is not None else 0
    theme.draw_text(surface, f"{label} {round(value)}%", (x, y), 13, theme.BROWN, bold=True)
    bar_rect = pygame.Rect(x, y + 17, width, 8)
    pygame.draw.rect(surface, theme.CREAM_DARK, bar_rect, border_radius=4)
    fill_w = max(4, int(bar_rect.width * min(1.0, value / 100)))
    pygame.draw.rect(surface, bar_color, (bar_rect.x, bar_rect.y, fill_w, bar_rect.height), border_radius=4)


def _draw_footer(surface, w, h, s):
    mac_stats = s.get("mac_stats") or {}
    if not mac_stats:
        return

    margin, gap = 16, 16
    meter_w = (w - margin * 2 - gap) // 2
    meter_y = h - 32

    _draw_meter(surface, margin, meter_w, meter_y, "CPU", mac_stats.get("cpu_percent"), theme.TERRACOTTA)
    _draw_meter(surface, margin + meter_w + gap, meter_w, meter_y, "RAM", mac_stats.get("mem_percent"), theme.MUSTARD)


def _render_loop(fb):
    surface = pygame.Surface((fb.width, fb.height))
    artwork_cache = {"b64": None, "surf": None}

    while True:
        with _state_lock:
            s = dict(_state)

        # Absolute epoch time, not elapsed-since-start — _handle_tap
        # records _button_flash timestamps with time.time() too, and
        # comparing an elapsed-time t against an absolute one made the
        # flash-duration check always true after the first tap (t was
        # tiny, flash_at was ~1.7 billion, so t - flash_at was hugely
        # negative and always "recent").
        t = time.time()

        surface.fill(theme.CREAM)
        _draw_header(surface, fb.width, s)
        is_playing = _draw_now_playing(surface, fb.width, s, artwork_cache, t)
        _draw_buttons(surface, is_playing, t)
        _draw_footer(surface, fb.width, fb.height, s)

        fb.blit(surface)
        # This panel's SPI link is configured at 16MHz (see config.txt);
        # a full 480x320x16bpp frame is ~300KB, which physically takes
        # ~150ms to shift over that bus — a hard ceiling around 6-7fps.
        # Targeting a higher rate just queues up frames faster than the
        # bus can drain them, which reads as stutter/freezing rather
        # than smoothness.
        time.sleep(1 / 7)


def _handle_tap(x, y):
    for bx, by, bw, bh, command in _BUTTONS:
        if bx <= x < bx + bw and by <= y < by + bh:
            print(f"Tap -> {command}")
            with _flash_lock:
                _button_flash[command] = time.time()
            send_command(command)
            return


def main():
    pygame.init()
    fb = Framebuffer()
    print(f"Framebuffer: {fb.width}x{fb.height}")
    threading.Thread(target=_server_loop, daemon=True).start()
    start_touch_listener(fb.width, fb.height, _handle_tap)
    _render_loop(fb)


if __name__ == "__main__":
    main()
