import httpx
import pytest

from shared import store, tools_impl, weather


def _mock_transport(handler):
    real = httpx.Client

    def factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        return real(*a, **kw)
    return factory


def test_geocode_and_forecast_are_compact(monkeypatch):
    def handler(req):
        if "geocoding" in req.url.host:
            return httpx.Response(200, json={"results": [
                {"name": "Haifa", "country": "Israel", "latitude": 32.81556, "longitude": 34.98917, "elevation": 0}]})
        return httpx.Response(200, json={"daily": {
            "time": ["2026-10-30", "2026-10-31"],
            "temperature_2m_min": [17.4, 18.1], "temperature_2m_max": [26.2, 27.9],
            "precipitation_sum": [0.0, 1.24], "weather_code": [1, 61]},
            "hourly": {"huge": list(range(500))}})
    monkeypatch.setattr(weather.httpx, "Client", _mock_transport(handler))

    g = tools_impl.geocode(city="Haifa")
    assert g == {"name": "Haifa", "country": "Israel", "lat": 32.816, "lon": 34.989}
    f = tools_impl.get_forecast(lat=g["lat"], lon=g["lon"], days=2)
    assert f["days"][1] == {"date": "2026-10-31", "tmin": 18, "tmax": 28, "rain_mm": 1.2, "code": 61}
    assert "hourly" not in str(f)
    assert [e["tool"] for e in store.read_tool_log()] == ["geocode", "get_forecast"]


def test_geocode_unknown_city_raises_and_is_logged(monkeypatch):
    monkeypatch.setattr(weather.httpx, "Client", _mock_transport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(ValueError):
        tools_impl.geocode(city="Nowhereville")
    assert store.read_tool_log()[-1]["ok"] is False


def test_save_itinerary_appends():
    tools_impl.save_itinerary(destination="Haifa", days=[{"day": 1, "plan": "Bahai"}, {"day": 2, "plan": "beach"}], budget=800)
    out = tools_impl.save_itinerary(destination="Eilat", days=["dive"], budget=3000)
    trips = store.read_json("trips.json", [])
    assert out == {"saved": True, "trip_id": 2, "n_days": 1}
    assert [t["destination"] for t in trips] == ["Haifa", "Eilat"]


def test_save_itinerary_rejects_empty():
    with pytest.raises(ValueError):
        tools_impl.save_itinerary(destination="Haifa", days=[])


def test_remember_supersedes_but_keeps_history():
    tools_impl.remember(key="Budget", value="800 NIS")
    out = tools_impl.remember(key="budget", value="3000 NIS")
    assert out == {"saved": "budget", "superseded": "800 NIS"}
    prefs = store.read_json("memory.json", {})["preferences"]
    assert [(p["value"], p["status"]) for p in prefs] == [("800 NIS", "superseded"), ("3000 NIS", "active")]


def test_recall_filters_by_query_and_includes_last_trip():
    tools_impl.remember(key="budget", value="800 NIS")
    tools_impl.remember(key="hiking", value="dislikes long hikes")
    tools_impl.save_itinerary(destination="Haifa", days=["a", "b"], budget=800)
    r = tools_impl.recall(query="hiking")
    assert r["preferences"] == [{"key": "hiking", "value": "dislikes long hikes"}]
    assert r["last_trip"].startswith("#1 Haifa, 2 days")


def test_packing_list_rules():
    items = tools_impl.packing_list(min_temp=10, max_temp=30, rain=True, activities=["desert hike"])["items"]
    for x in ("warm jacket", "hat", "umbrella", "hiking shoes"):
        assert x in items
