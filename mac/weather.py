"""
Open-Meteo current-weather fetch — free, no API key required.

Location is auto-detected once via IP geolocation (ip-api.com, also
free/keyless) and cached for the process lifetime — good enough for a
laptop that mostly sits in one place; not meant for precise or
frequently-moving use.
"""
import json
import ssl
import time
import urllib.request

import certifi

from config import WEATHER_REFRESH_S

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

_location_cache = {"lat": None, "lon": None}
_cache = {"data": None, "fetched_at": 0.0}


def _detect_location():
    if _location_cache["lat"] is not None:
        return _location_cache["lat"], _location_cache["lon"]
    try:
        url = "http://ip-api.com/json/?fields=lat,lon,city"
        with urllib.request.urlopen(url, timeout=5) as resp:
            info = json.load(resp)
        _location_cache["lat"] = info["lat"]
        _location_cache["lon"] = info["lon"]
        print(f"Weather location auto-detected: {info.get('city')} ({info['lat']}, {info['lon']})")
    except Exception as e:
        print("IP geolocation failed, weather disabled:", e)
    return _location_cache["lat"], _location_cache["lon"]


def get_weather():
    now = time.time()
    if _cache["data"] is not None and now - _cache["fetched_at"] < WEATHER_REFRESH_S:
        return _cache["data"]

    lat, lon = _detect_location()
    if lat is None:
        return _cache["data"] or {}

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code"
    )
    try:
        with urllib.request.urlopen(url, timeout=5, context=_SSL_CONTEXT) as resp:
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
