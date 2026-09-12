"""
Gathers local Mac state: battery, now-playing (via `media-control`), and
system stats.

Now-playing uses `media-control stream --micros` as a persistent
background process (the tool's own recommended pattern — see its
examples/now-playing-live.py) so updates arrive in near real time
without repeatedly spawning subprocesses. Battery/stats are cheap
enough to just poll on each push instead.

Requires:
    brew install media-control
    pip3 install psutil
"""
import json
import re
import subprocess
import threading
import time

import psutil

_EMPTY_NOW_PLAYING = {
    "title": None,
    "artist": None,
    "album": None,
    "artwork_b64": None,
    "playing": False,
    "elapsed_s": 0.0,
    "duration_s": 0.0,
    "updated_epoch": 0.0,
}

_now_playing_lock = threading.Lock()
_now_playing = dict(_EMPTY_NOW_PLAYING)

# CLI subcommand names `media-control` actually accepts, mapped from the
# short names we use in the over-the-wire command protocol.
_COMMAND_MAP = {
    "play": "play",
    "pause": "pause",
    "toggle": "toggle-play-pause",
    "next": "next-track",
    "previous": "previous-track",
}


def _now_playing_stream_loop():
    global _now_playing
    proc = subprocess.Popen(
        ["media-control", "stream", "--micros"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    for line in proc.stdout:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        payload = msg.get("payload", {})
        if not msg.get("diff", True) and not payload:
            # Nothing playing / playback session ended.
            with _now_playing_lock:
                _now_playing = dict(_EMPTY_NOW_PLAYING)
                _now_playing["updated_epoch"] = time.time()
            continue

        with _now_playing_lock:
            if payload.get("title") is not None:
                _now_playing["title"] = payload["title"]
            if payload.get("artist") is not None:
                _now_playing["artist"] = payload["artist"]
            if payload.get("album") is not None:
                _now_playing["album"] = payload["album"]
            if payload.get("artworkData") is not None:
                _now_playing["artwork_b64"] = payload["artworkData"]
            if payload.get("playing") is not None:
                _now_playing["playing"] = payload["playing"]
            if payload.get("elapsedTimeMicros") is not None:
                _now_playing["elapsed_s"] = payload["elapsedTimeMicros"] / 1_000_000
            if payload.get("durationMicros") is not None:
                _now_playing["duration_s"] = payload["durationMicros"] / 1_000_000
            _now_playing["updated_epoch"] = time.time()


def start_now_playing_stream():
    threading.Thread(target=_now_playing_stream_loop, daemon=True).start()


def get_now_playing():
    with _now_playing_lock:
        return dict(_now_playing)


def get_battery():
    out = subprocess.run(
        ["pmset", "-g", "batt"], capture_output=True, text=True
    ).stdout
    match = re.search(r"(\d+)%", out)
    percent = int(match.group(1)) if match else None
    charging = "AC Power" in out
    return {"percent": percent, "charging": charging}


def get_mac_stats():
    return {
        "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
        "mem_percent": round(psutil.virtual_memory().percent, 1),
        "uptime_s": int(time.time() - psutil.boot_time()),
    }


def run_command(command):
    """Execute a playback command received from the Pi's touchscreen."""
    cli_cmd = _COMMAND_MAP.get(command)
    if cli_cmd is None:
        print(f"Unknown command: {command!r}")
        return
    subprocess.run(["media-control", cli_cmd])
