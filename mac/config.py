"""Shared config for the Mac-side push client."""
import os

# Override at runtime with: PI_HOST=192.168.x.x python3 push_client.py
# (kept out of this file so the real LAN IP never ends up in git history)
PI_HOST = os.environ.get("PI_HOST", "pi.local")
PI_PORT = int(os.environ.get("PI_PORT", "8765"))

# Open-Meteo (https://open-meteo.com) needs no API key, just coordinates.
# REPLACE these with your actual location.
WEATHER_LAT = 53.3498
WEATHER_LON = -6.2603
WEATHER_REFRESH_S = 30 * 60
