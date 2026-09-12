"""Open-Meteo current-weather fetch — free, no API key required."""
import json
import ssl
import time
import urllib.request

import certifi

from config import WEATHER_LAT, WEATHER_LON, WEATHER_REFRESH_S

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
    "&current=temperature_2m,weather_code"
)

_cache = {"data": None, "fetched_at": 0.0}


def get_weather():
    now = time.time()
    if _cache["data"] is not None and now - _cache["fetched_at"] < WEATHER_REFRESH_S:
        return _cache["data"]
    try:
        with urllib.request.urlopen(_URL, timeout=5, context=_SSL_CONTEXT) as resp:
            payload = json.load(resp)
        current = payload.get("current", {})
        data = {
            "temp_c": current.get("temperature_2m"),
            "weather_code": current.get("weather_code"),
        }
        _cache["data"] = data
        _cache["fetched_at"] = now
        return data
    except Exception as e:
        print("weather fetch failed:", e)
        return _cache["data"] or {}
