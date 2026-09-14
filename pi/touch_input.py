"""
Reads the ADS7846/XPT2046 touchscreen (/dev/input/event0, found via
discover_touch.py) and calls a callback with calibrated screen pixel
coordinates once per tap.

Calibration below comes from tapping all four screen corners: this
panel's raw ADC range doesn't use the full 0-4095 sweep. Which axis
reads inverted depends on the display's `rotate=` setting in
config.txt — the overlay ties touch orientation to it. Back on
rotate=90 (the original setting): X reads inverted, Y reads direct.
(At rotate=270 it was the opposite — X direct, Y inverted — see git
history if switching back to that rotation.) If taps land in the
wrong spot after changing rotation again, re-run discover_touch.py and
adjust the RAW_*_MIN/MAX constants and the invert direction below.
"""
import threading

import evdev

DEVICE_PATH = "/dev/input/event0"

RAW_X_MIN, RAW_X_MAX = 460, 3780  # right edge -> left edge (X is inverted)
RAW_Y_MIN, RAW_Y_MAX = 320, 3680  # top edge -> bottom edge (Y is direct)


def _calibrate(raw_x, raw_y, width, height):
    x = (RAW_X_MAX - raw_x) / (RAW_X_MAX - RAW_X_MIN) * width
    y = (raw_y - RAW_Y_MIN) / (RAW_Y_MAX - RAW_Y_MIN) * height
    x = max(0, min(width - 1, x))
    y = max(0, min(height - 1, y))
    return int(x), int(y)


def start_touch_listener(width, height, on_tap):
    """on_tap(x, y) fires once per tap-release, in screen pixel coords."""

    def _loop():
        dev = evdev.InputDevice(DEVICE_PATH)
        raw_x = raw_y = None
        touching = False
        for event in dev.read_loop():
            if event.type == evdev.ecodes.EV_ABS:
                if event.code == evdev.ecodes.ABS_X:
                    raw_x = event.value
                elif event.code == evdev.ecodes.ABS_Y:
                    raw_y = event.value
            elif event.type == evdev.ecodes.EV_KEY and event.code == evdev.ecodes.BTN_TOUCH:
                if event.value == 1:
                    touching = True
                elif event.value == 0 and touching:
                    touching = False
                    if raw_x is not None and raw_y is not None:
                        on_tap(*_calibrate(raw_x, raw_y, width, height))

    threading.Thread(target=_loop, daemon=True).start()
