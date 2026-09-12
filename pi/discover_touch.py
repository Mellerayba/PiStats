"""
One-off diagnostic: lists input devices and, for anything that looks
like a touchscreen, prints its ABS_X/ABS_Y range. Used to find the
XPT2046 touch device path and calibration range before wiring up
touch_input.py.

Requires: sudo apt install -y python3-evdev

Run on the Pi with:
    python3 discover_touch.py
Then tap the screen a few times while it's running (in the "watch raw
events" section) to see live coordinates.
"""
import evdev

devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

if not devices:
    print("No input devices found at all — check evdev is reading /dev/input.")

for dev in devices:
    print(f"{dev.path}: {dev.name}")
    caps = dev.capabilities(verbose=True)
    abs_caps = caps.get(("EV_ABS", 3), [])
    for (code_name, code), absinfo in abs_caps:
        print(f"    {code_name}: min={absinfo.min} max={absinfo.max}")

touch_candidates = [
    d for d in devices
    if any(k in d.name.lower() for k in ("touch", "ads7846", "xpt", "stmpe", "ft5"))
]

if not touch_candidates:
    print("\nNo obviously-named touch device found — inspect the list above manually.")
else:
    dev = touch_candidates[0]
    print(f"\nWatching raw touch events on {dev.path} ({dev.name}) — tap the screen, Ctrl+C to stop.")
    for event in dev.read_loop():
        if event.type == evdev.ecodes.EV_ABS:
            code_name = evdev.ecodes.ABS[event.code]
            print(f"  ABS {code_name} = {event.value}")
        elif event.type == evdev.ecodes.EV_KEY:
            print(f"  KEY {evdev.ecodes.keys.get(event.code, event.code)} = {event.value}")
