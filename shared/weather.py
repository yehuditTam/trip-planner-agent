"""Open-Meteo client (free, no API key). Returns compact dicts, never the raw payload."""
import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10.0


def geocode(city: str, client: httpx.Client | None = None) -> dict:
    c = client or httpx.Client(timeout=TIMEOUT)
    r = c.get(GEOCODE_URL, params={"name": city, "count": 1, "language": "en", "format": "json"})
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise ValueError(f"city not found: {city}")
    top = results[0]
    return {
        "name": top["name"],
        "country": top.get("country", ""),
        "lat": round(top["latitude"], 3),
        "lon": round(top["longitude"], 3),
    }


def forecast(lat: float, lon: float, days: int = 3, client: httpx.Client | None = None) -> list[dict]:
    c = client or httpx.Client(timeout=TIMEOUT)
    r = c.get(FORECAST_URL, params={
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
        "forecast_days": max(1, min(days, 7)),
        "timezone": "auto",
    })
    r.raise_for_status()
    d = r.json()["daily"]
    # Compact: ~25 tokens per day instead of the full hourly/units payload.
    return [
        {
            "date": d["time"][i],
            "tmin": round(d["temperature_2m_min"][i]),
            "tmax": round(d["temperature_2m_max"][i]),
            "rain_mm": round(d["precipitation_sum"][i] or 0, 1),
            "code": d["weather_code"][i],
        }
        for i in range(len(d["time"]))
    ]
