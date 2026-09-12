"""
Pi-side socket server: accepts a connection from the Mac, receives its
pushed state (battery, now-playing + artwork, system stats, weather) as
newline-delimited JSON, and renders it to the piscreen panel using the
Pi's own system clock for the time/date display.

Touch (previous/play-pause/next, via the XPT2046 touchscreen) sends
playback commands back to the Mac over the same connection.

Requires: sudo apt install -y python3-evdev fonts-symbola

Run on the Pi with:
    python3 state_server.py
"""
import base64
import io
import json
import socket
import threading
import time

import pygame

from fb_display import Framebuffer
from touch_input import start_touch_listener

HOST = "0.0.0.0"
PORT = 8765

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (120, 120, 120)
GREEN = (40, 160, 60)

# WMO weather codes (as returned by Open-Meteo) mapped to Unicode symbols.
# Deliberately using older "Miscellaneous Symbols" glyphs (U+2600 block)
# rather than modern color emoji — pygame's font rendering on Linux only
# draws monochrome outlines, and DejaVu Sans (the usual default) covers
# this block far more reliably than newer emoji code points.
_WEATHER_SYMBOLS = {
    0: "☀",  # clear sky
    1: "☀",  # mainly clear
    2: "☁",  # partly cloudy
    3: "☁",  # overcast
    45: "=",  # fog (no reliable glyph, fall back to a plain mark)
    48: "=",
    51: "☔", 53: "☔", 55: "☔",  # drizzle
    56: "☔", 57: "☔",  # freezing drizzle
    61: "☔", 63: "☔", 65: "☔",  # rain
    66: "☔", 67: "☔",  # freezing rain
    71: "❄", 73: "❄", 75: "❄", 77: "❄",  # snow
    80: "☔", 81: "☔", 82: "☔",  # rain showers
    85: "❄", 86: "❄",  # snow showers
    95: "⚡", 96: "⚡", 99: "⚡",  # thunderstorm
}

_state_lock = threading.Lock()
_state = {}

_client_lock = threading.Lock()
_client_conn = None

# (x, y, w, h, label, command) — command matches mac/state_source.py's
# _COMMAND_MAP keys.
_BUTTONS = [
    (10, 235, 140, 45, "<<", "previous"),
    (170, 235, 140, 45, "> ||", "toggle"),  # label is overridden dynamically in the render loop
    (330, 235, 140, 45, ">>", "next"),
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
                chunk = conn.recv(4096)
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
            _handle_client(conn, addr)  # one Mac at a time is fine


def _render_loop(fb):
    font_med = pygame.font.SysFont(None, 28)
    font_small = pygame.font.SysFont(None, 22)
    # pygame's bundled default font and DejaVu Sans both lack these
    # Unicode symbol glyphs (render as tofu boxes) — Symbola has full
    # coverage. Install with: sudo apt install -y fonts-symbola
    font_symbol = pygame.font.SysFont("symbola", 22)
    surface = pygame.Surface((fb.width, fb.height))
    artwork_cache = {"b64": None, "surf": None}

    while True:
        with _state_lock:
            s = dict(_state)

        surface.fill(WHITE)

        # --- clock (Pi's own system time, per the earlier decision) ---
        surface.blit(font_med.render(time.strftime("%H:%M:%S"), True, BLACK), (10, 6))
        surface.blit(font_small.render(time.strftime("%a %d %b"), True, GRAY), (10, 30))

        # --- battery ---
        batt = s.get("battery") or {}
        batt_text = f"{batt.get('percent', '?')}%" + (" chg" if batt.get("charging") else "")
        surface.blit(font_med.render(batt_text, True, BLACK), (fb.width - 90, 6))

        # --- weather ---
        wx = s.get("weather") or {}
        if wx.get("temp_c") is not None:
            symbol = _WEATHER_SYMBOLS.get(wx.get("weather_code"), "")
            temp_x = fb.width - 90
            if symbol:
                symbol_surf = font_symbol.render(symbol, True, GRAY)
                surface.blit(symbol_surf, (temp_x, 28))
                temp_x += symbol_surf.get_width() + 4
            surface.blit(font_small.render(f"{wx['temp_c']}C", True, GRAY), (temp_x, 30))

        # --- now playing ---
        np_ = s.get("now_playing") or {}
        artwork_b64 = np_.get("artwork_b64")
        if artwork_b64 and artwork_b64 != artwork_cache["b64"]:
            try:
                raw = base64.b64decode(artwork_b64)
                img = pygame.image.load(io.BytesIO(raw))
                img = pygame.transform.smoothscale(img, (140, 140))
                artwork_cache["b64"] = artwork_b64
                artwork_cache["surf"] = img
            except Exception as e:
                print("artwork decode failed:", e)
        elif not artwork_b64:
            artwork_cache["b64"] = None
            artwork_cache["surf"] = None

        art_x, art_y = 10, 70
        if artwork_cache["surf"]:
            surface.blit(artwork_cache["surf"], (art_x, art_y))
        else:
            pygame.draw.rect(surface, GRAY, (art_x, art_y, 140, 140), 2)

        text_x = art_x + 155
        surface.blit(font_med.render((np_.get("title") or "Nothing playing")[:22], True, BLACK), (text_x, art_y))
        surface.blit(font_small.render((np_.get("artist") or "")[:26], True, GRAY), (text_x, art_y + 28))
        surface.blit(font_small.render((np_.get("album") or "")[:26], True, GRAY), (text_x, art_y + 50))

        # Extrapolate elapsed time between pushes so the bar doesn't
        # visibly stall between the Mac's once-a-second updates.
        elapsed = np_.get("elapsed_s") or 0.0
        duration = np_.get("duration_s") or 0.0
        updated_epoch = np_.get("updated_epoch") or 0.0
        if np_.get("playing") and updated_epoch:
            elapsed += max(0.0, time.time() - updated_epoch)
        if duration:
            bar_w = fb.width - 20
            pygame.draw.rect(surface, GRAY, (10, art_y + 150, bar_w, 6), 1)
            frac = max(0.0, min(1.0, elapsed / duration))
            pygame.draw.rect(surface, GREEN, (10, art_y + 150, int(bar_w * frac), 6))

        # --- playback buttons ---
        is_playing = bool(np_.get("playing"))
        for x, y, w, h, label, cmd in _BUTTONS:
            if cmd == "toggle":
                label = "||" if is_playing else ">"
            pygame.draw.rect(surface, GRAY, (x, y, w, h), 2)
            label_surf = font_med.render(label, True, BLACK)
            lx = x + (w - label_surf.get_width()) // 2
            ly = y + (h - label_surf.get_height()) // 2
            surface.blit(label_surf, (lx, ly))

        # --- mac stats ---
        mac_stats = s.get("mac_stats") or {}
        if mac_stats:
            stats_text = f"Mac CPU {mac_stats.get('cpu_percent', '?')}%  RAM {mac_stats.get('mem_percent', '?')}%"
            surface.blit(font_small.render(stats_text, True, GRAY), (10, fb.height - 22))

        fb.blit(surface)
        time.sleep(1 / 15)


def _handle_tap(x, y):
    for bx, by, bw, bh, _label, command in _BUTTONS:
        if bx <= x < bx + bw and by <= y < by + bh:
            print(f"Tap -> {command}")
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
