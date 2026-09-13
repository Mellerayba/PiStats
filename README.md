# PiStats

A mid-century-modern desk display, built on a Raspberry Pi 3, that shows
live now-playing (with album art), battery, weather, and system stats
pulled from a Mac over the local network — with touch controls for
play/pause/skip.

Built as a learning project, and as an experiment in building on real
hardware with [Claude Code](https://claude.com/claude-code) driving
most of the implementation.

![status](https://img.shields.io/badge/status-working-brightgreen)

## What it does

- **Now playing**: title, artist, album, and artwork, pulled from macOS
  via [`media-control`](https://github.com/ungive/media-control) and
  pushed to the Pi in real time, with a progress bar and touch controls
  (previous / play-pause / next) that send commands back to the Mac.
- **Battery**: percentage and charging state, via `pmset`.
- **Weather**: current temperature and conditions, auto-detected
  location via IP geolocation, no API key required (Open-Meteo).
- **System stats**: the Mac's CPU/RAM usage as live meters.
- **Clock**: the Pi's own system time, atomic-age starburst motif
  because it's a clock.

Both sides auto-start with no manual SSH-in: `systemd` on the Pi,
`launchd` on the Mac.

## Hardware

- Raspberry Pi 3 Model B
- A generic 3.5" 480×320 SPI TFT panel with an XPT2046 touch
  controller, driven by the mainlined `piscreen` device-tree overlay
- A Mac on the same local network as the data source

## Architecture

```
Mac (push_client.py)  <-- TCP socket, JSON -->  Pi (state_server.py)
  battery, now-playing,                            renders to the panel,
  weather, system stats                            sends touch taps back
      |                                                  |
  media-control, pmset,                            pygame -> mmap ->
  psutil, Open-Meteo                                /dev/fbN (no display
                                                     server involved)
```

The transport is a plain bidirectional TCP socket, not Bluetooth — see
[`Instructions.md`](Instructions.md) for why BLE was investigated and
abandoned (a genuine kernel/BlueZ compatibility bug on this Pi's
Bluetooth chip, not something fixable from application code).

Rendering writes raw RGB565 bytes directly into the framebuffer's
memory via `mmap`, bypassing `pygame.display` entirely — this OS's
SDL2 build has no usable driver for this class of SPI panel.

## Repo layout

- `pi/` — runs on the Raspberry Pi: framebuffer rendering
  (`fb_display.py`, `theme.py`), the socket server + UI
  (`state_server.py`), touch input (`touch_input.py`), and the
  `systemd` unit.
- `mac/` — runs on the Mac: gathers state (`state_source.py`,
  `weather.py`) and pushes it to the Pi (`push_client.py`), plus a
  `launchd` LaunchAgent template.
- `Instructions.md` — the full build log: hardware setup, every bug
  hit and how it was diagnosed/fixed, and the roadmap.

## Status

Working end-to-end: display driver, data pipeline, touch controls,
auto-start on both ends, and a from-scratch visual design pass. BLE
was investigated and deliberately dropped in favor of the working WiFi
transport. See `Instructions.md` for the detailed roadmap and the
technical writeups behind each decision.
