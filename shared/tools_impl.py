"""Domain tools: plain Python, no Claude. Both API/ and SDK/ wrap these same functions."""
import time
from datetime import datetime, timezone
from functools import wraps

from shared import store, weather

MEMORY_FILE = "memory.json"
TRIPS_FILE = "trips.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def logged(fn):
    """Record every call in tool_log.jsonl (success or failure), then re-raise errors."""
    @wraps(fn)
    def wrapper(**kwargs):
        t0 = time.perf_counter()
        try:
            out = fn(**kwargs)
            store.log_tool(fn.__name__, kwargs, True, (time.perf_counter() - t0) * 1000)
            return out
        except Exception:
            store.log_tool(fn.__name__, kwargs, False, (time.perf_counter() - t0) * 1000)
            raise
    return wrapper


def normalize_key(key: str) -> str:
    return "_".join(key.strip().lower().replace("-", " ").split())


# ---------- external (Open-Meteo) ----------

@logged
def geocode(city: str) -> dict:
    return weather.geocode(city)


@logged
def get_forecast(lat: float, lon: float, days: int = 3) -> dict:
    return {"days": weather.forecast(lat, lon, days)}


# ---------- trips (files) ----------

@logged
def save_itinerary(destination: str, days: list, budget: float | None = None) -> dict:
    if not destination.strip():
        raise ValueError("destination is required")
    if not days:
        raise ValueError("days must contain at least one day")
    trips = store.read_json(TRIPS_FILE, [])
    trip = {
        "id": len(trips) + 1,
        "destination": destination.strip(),
        "days": [d if isinstance(d, dict) else {"plan": str(d)} for d in days],
        "budget": budget,
        "saved_at": _now(),
    }
    trips.append(trip)
    store.write_json(TRIPS_FILE, trips)
    return {"saved": True, "trip_id": trip["id"], "n_days": len(trip["days"])}


@logged
def packing_list(style: str = "casual", min_temp: float | None = None,
                 max_temp: float | None = None, rain: bool = False, activities: list | None = None) -> dict:
    """Rule-based, no network. Returns a short list instead of prose to save tokens."""
    items = ["ID", "phone charger", "water bottle", "sunscreen"]
    if min_temp is not None and min_temp < 15:
        items.append("warm jacket")
    if max_temp is not None and max_temp >= 25:
        items += ["hat", "light clothes"]
    if rain:
        items += ["umbrella", "rain jacket"]
    acts = " ".join(activities or []).lower()
    if "hike" in acts or "hiking" in acts or "desert" in acts:
        items += ["hiking shoes", "3L water", "snacks"]
    if "beach" in acts or "swim" in acts:
        items += ["swimsuit", "towel"]
    if style.lower() in ("luxury", "fancy"):
        items.append("evening outfit")
    return {"items": sorted(set(items))}


# ---------- memory ----------

@logged
def remember(key: str, value: str) -> dict:
    """Save a preference. A new value for an existing key supersedes the old one (history is kept)."""
    k = normalize_key(key)
    mem = store.read_json(MEMORY_FILE, {"preferences": []})
    superseded = None
    for p in mem["preferences"]:
        if p["key"] == k and p["status"] == "active":
            if p["value"] == value:
                return {"saved": k, "unchanged": True}
            p["status"] = "superseded"
            p["superseded_at"] = _now()
            superseded = p["value"]
    mem["preferences"].append({"key": k, "value": value, "status": "active", "created_at": _now()})
    store.write_json(MEMORY_FILE, mem)
    return {"saved": k, "superseded": superseded}


def active_preferences() -> list[dict]:
    mem = store.read_json(MEMORY_FILE, {"preferences": []})
    return [{"key": p["key"], "value": p["value"]} for p in mem["preferences"] if p["status"] == "active"]


def last_trip_summary() -> str | None:
    trips = store.read_json(TRIPS_FILE, [])
    if not trips:
        return None
    t = trips[-1]
    return f"#{t['id']} {t['destination']}, {len(t['days'])} days, budget {t['budget']}"


@logged
def recall(query: str = "") -> dict:
    """Active preferences matching the query words (all if empty) + one-line last trip."""
    prefs = active_preferences()
    words = [w for w in normalize_key(query).split("_") if len(w) > 2]
    if words:
        prefs = [p for p in prefs if any(w in (p["key"] + " " + p["value"]).lower() for w in words)] or prefs
    return {"preferences": prefs, "last_trip": last_trip_summary()}
