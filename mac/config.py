"""Shared config for the Mac-side push client."""

PI_HOST = "pi.local"  # replace with your Pi's actual LAN IP/hostname
PI_PORT = 8765

# Open-Meteo (https://open-meteo.com) needs no API key, just coordinates.
# REPLACE these with your actual location.
WEATHER_LAT = 53.3498
WEATHER_LON = -6.2603
WEATHER_REFRESH_S = 30 * 60
