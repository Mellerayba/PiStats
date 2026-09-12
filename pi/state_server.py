"""
Pi-side socket server: accepts a connection from the Mac, receives its
pushed state (battery, now-playing + artwork, system stats, weather) as
newline-delimited JSON, and renders it to the piscreen panel using the
Pi's own system clock for the time/date display.

Also the endpoint for touch-driven playback commands sent back to the
Mac over the same connection — the wire protocol and send_command()
plumbing are ready, but nothing calls send_command() yet: reading the
XPT2046 touch controller (as a Linux evdev input device) and mapping
taps to on-screen button regions is the next step, not built here.

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

HOST = "0.0.0.0"
PORT = 8765

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (120, 120, 120)
GREEN = (40, 160, 60)

_state_lock = threading.Lock()
_state = {}

_client_lock = threading.Lock()
_client_conn = None


def send_command(command):
    """Send a playback command back to the Mac. Not called anywhere yet —
    wired up once touch input is built."""
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
            surface.blit(font_small.render(f"{wx['temp_c']}C", True, GRAY), (fb.width - 90, 30))

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

        # --- mac stats ---
        mac_stats = s.get("mac_stats") or {}
        if mac_stats:
            stats_text = f"Mac CPU {mac_stats.get('cpu_percent', '?')}%  RAM {mac_stats.get('mem_percent', '?')}%"
            surface.blit(font_small.render(stats_text, True, GRAY), (10, fb.height - 22))

        fb.blit(surface)
        time.sleep(1 / 15)


def main():
    pygame.init()
    fb = Framebuffer()
    print(f"Framebuffer: {fb.width}x{fb.height}")
    threading.Thread(target=_server_loop, daemon=True).start()
    _render_loop(fb)


if __name__ == "__main__":
    main()
