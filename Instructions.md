# Pi Info Display Project

## Goal
A Raspberry Pi 3 with a small GPIO-mounted display, connected wirelessly to a
Mac, showing live info: battery level, currently playing song, and other
"cool" at-a-glance data. Built as a learning project (CS undergrad),
not just to get it working but to understand the pieces.

## Hardware
- **Raspberry Pi 3 Model B**
- **3.5" TFT display, 480x320, XPT2046 touch controller** — a generic
  clone board, GPIO-mounted (no HDMI needed once driver is installed).
  Compatible with the built-in `piscreen` device-tree overlay.
- Mac (development machine, target data source: battery %, now-playing info)
- A capture card was used temporarily to view HDMI boot output without
  needing a keyboard (Pi's power supply couldn't spare current for
  peripherals when sharing power with a large monitor). Long-term, a
  self-powered USB hub is worth getting if physical peripheral access is
  needed again.

## Current OS / network state
- **OS**: Raspberry Pi OS Lite, "Raspbian GNU/Linux 13" (Trixie), 32-bit,
  flashed via Raspberry Pi Imager.
- **Headless setup**: WiFi + SSH were configured through Imager's
  gear-icon settings (General tab: SSID/password/**WiFi country** — this
  field is easy to miss and if unset, the WiFi radio stays disabled
  entirely on Pi 3B+ and later; General tab also has hostname/user;
  Services tab enables SSH).
- **SSH login**: `root` login is disabled by default — must SSH in as the
  custom username created in Imager, not `root`.
  - Username/password/IP: kept out of this repo (see local-only notes) —
    still a placeholder password, **change it** before the Pi is exposed
    to anything beyond a trusted home network.
- **Known gotcha**: after re-flashing the SD card, the Pi gets a new SSH
  host key, which makes the Mac refuse to connect with a "host key
  verification failed" warning. Fix: `ssh-keygen -R <ip-or-hostname>`
  then reconnect and accept the new fingerprint.
- Connect with: `ssh <username>@<pi-ip>` (see local-only notes for actual values)

## Display driver — DONE and working
The 3.5" XPT2046 panel is driven by the built-in `piscreen` overlay
(no need for third-party install scripts like LCD-show on this OS
version — it's mainlined).

Steps already completed:
1. Enabled SPI via `sudo raspi-config` → Interface Options → SPI.
2. Added this line to the bottom of `/boot/firmware/config.txt`
   (note: **not** `/boot/config.txt` — the path moved under
   `/boot/firmware/` on Bookworm/Trixie):
   ```
   dtoverlay=piscreen,speed=16000000,rotate=90
   ```
3. Rebooted. The screen now renders as a second framebuffer device,
   `/dev/fb1`, and shows real console output instead of a blank white
   screen.
- Rotation (`rotate=90` currently set) can be changed to `0`/`180`/`270`
  if orientation needs adjusting once a real app is running.

## Architecture plan (not yet built)

**Rendering on the Pi:**
Use Python + `pygame`, targeting the framebuffer directly via environment
variables:
```
SDL_VIDEODRIVER=fbcon
SDL_FBDEV=/dev/fb1
```
This avoids needing a desktop environment/X11/browser stack, which
matters on a Pi 3's limited resources. (Alternative considered and
rejected for now: X11 + Chromium kiosk mode — heavier, more polished
visually, more fragile on this hardware.)

**Getting data off the Mac:**
- **Now playing**: use `media-control` (`brew install media-control`,
  from `ungive/media-control` on GitHub) or `nowplaying-cli` — both wrap
  Apple's private `MediaRemote` framework and return track/artist/album
  as JSON/text with no custom native code needed.
- **Battery**: `pmset -g batt` (trivial to parse) or IOKit power source
  APIs if going native.

**Transport (Mac → Pi):**
Decision: prefer **BLE** over classic Bluetooth SPP, because macOS's
Bluetooth APIs lean toward `CoreBluetooth` (BLE) rather than raw RFCOMM
serial sockets these days.
- Pi side: `bluezero` or `bleak` (Python, on top of BlueZ) — likely as a
  BLE peripheral advertising a custom GATT characteristic that the Mac
  connects to and writes to.
- Mac side: `bleak` (cross-platform BLE lib) as the central.
- **Recommended de-risking step**: build and test the whole pipeline
  first over a plain local socket (same WiFi network) before swapping in
  BLE, so rendering/data-format bugs and Bluetooth-specific bugs aren't
  being debugged at the same time.

## Roadmap / next steps
1. [x] Pygame "hello world" script rendering to `/dev/fb1` — confirms
       app-level rendering works (not just console mirroring).
       **Gotcha discovered**: this OS's SDL2 (from apt's `python3-pygame`)
       has no `fbdev` video driver compiled in (only x11/wayland/KMSDRM/
       offscreen/dummy/evdev), and KMSDRM doesn't apply either since
       fbtft-style panels like piscreen expose `/dev/fbN`, not a DRM
       device. Working approach: render to an off-screen `pygame.Surface`
       (no display driver needed), pack to RGB565, and write raw bytes
       into `/dev/fb1` via `mmap`. See `pi/hello_world.py`.
2. [x] Mac-side script: pull battery + now-playing, push over a plain
       local socket to the Pi. Confirms the data pipeline end-to-end.
       Built as `mac/state_source.py` + `mac/weather.py` + `mac/push_client.py`.
       Weather location is auto-detected via IP geolocation. Bidirectional:
       also listens on the same socket for playback commands from the Pi.
3. [x] Pi-side: receive over socket, render to screen. Built as
       `pi/state_server.py`. Also added touch controls (previous/play-pause/
       next) via `pi/touch_input.py`, reading the XPT2046 touchscreen
       through evdev — see `pi/discover_touch.py` for how it was calibrated.
4. [ ] Swap plain socket for BLE (Pi as peripheral, Mac as central via
       `bleak`).
5. [ ] Real UI/design pass on the display output.
6. [x] `systemd` service unit so the Pi's app launches automatically on
       boot (no manual SSH-in-and-run needed). `pi/piscreen-display.service`,
       verified surviving a real `sudo reboot`. Mac-side equivalent also
       done: `mac/com.pistats.pushclient.plist.template` (a launchd
       LaunchAgent). **Gotcha**: a launchd-spawned python3 process got
       `[Errno 65] No route to host` on every socket connection, even
       though raw `nc` worked fine — macOS's Local Network privacy
       permission (System Settings → Privacy & Security → Local Network)
       blocks headless background processes since they can't show the
       grant prompt themselves; had to enable it manually once.

## Open questions / things to decide next
- Exact GATT characteristic/service design for the BLE link (or whether
  to just stick with a lightweight local-network protocol like MQTT and
  drop true Bluetooth as a hard requirement).
- Update/security posture for the placeholder `1234` password before
  this leaves a trusted network.
