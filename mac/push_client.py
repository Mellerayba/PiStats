"""
Mac-side push client: connects to the Pi and streams state (battery,
now-playing, system stats, weather) as newline-delimited JSON. Listens
on the same socket for playback commands sent back from the Pi's
touchscreen and executes them via `media-control`.

Run on the Mac with:
    python3 push_client.py
"""
import json
import socket
import threading
import time

import state_source
import weather
from config import PI_HOST, PI_PORT

PUSH_INTERVAL_S = 1.0


def reader_loop(sock):
    buf = b""
    while True:
        chunk = sock.recv(4096)
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
            if msg.get("type") == "command":
                state_source.run_command(msg.get("command"))


def main():
    state_source.start_now_playing_stream()
    while True:
        try:
            print(f"Connecting to {PI_HOST}:{PI_PORT}...")
            with socket.create_connection((PI_HOST, PI_PORT), timeout=5) as sock:
                print("Connected.")
                threading.Thread(target=reader_loop, args=(sock,), daemon=True).start()
                while True:
                    payload = {
                        "battery": state_source.get_battery(),
                        "now_playing": state_source.get_now_playing(),
                        "mac_stats": state_source.get_mac_stats(),
                        "weather": weather.get_weather(),
                    }
                    sock.sendall((json.dumps(payload) + "\n").encode())
                    time.sleep(PUSH_INTERVAL_S)
        except OSError as e:
            print(f"Connection lost/failed ({e}), retrying in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    main()
