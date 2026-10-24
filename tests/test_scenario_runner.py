"""The scenario runner and assertions, end to end, driven by the API agent on a scripted mock client."""
import json
from pathlib import Path

from API.agent import TripAgent
from shared import loc
from shared.scenario_runner import run_scenario
from tests.fakes import FakeClient, reply, text, tool_use

ROOT = Path(__file__).resolve().parent.parent
FORECAST = {"days": [{"date": "2026-10-30", "tmin": 20, "tmax": 28, "rain_mm": 0, "code": 1}]}


def script():
    """What a well-behaved model would do in each scenario turn."""
    return [
        # session 1
        reply(tool_use("remember", key="budget", value="800 NIS"), tool_use("remember", key="hiking", value="dislikes long hikes")),
        reply(text("Saved.")),
        reply(tool_use("get_forecast", lat=32.8, lon=35.0, days=2)),
        reply(text("Sunny, 20-28C.")),
        reply(tool_use("save_itinerary", destination="Haifa", days=[{"day": 1, "plan": "Bahai"}, {"day": 2, "plan": "beach"}], budget=800)),
        reply(text("Saved your Haifa plan.")),
        reply(tool_use("packing_list", min_temp=20, max_temp=28)),
        reply(text("Hat, sunscreen.")),
        # session 2
        reply(text("Budget 800 NIS, no long hikes; last trip Haifa.")),
        reply(tool_use("remember", key="budget", value="3000 NIS"), tool_use("remember", key="hiking", value="wants a long desert hike")),
        reply(text("Updated.")),
        reply(tool_use("save_itinerary", destination="Eilat", days=[{"day": 1, "plan": "hike"}, {"day": 2, "plan": "reef"}], budget=3000)),
        reply(text("Saved.")),
    ]


def test_full_scenario_offline(tmp_path, monkeypatch):
    from shared import tools_impl
    monkeypatch.setattr(tools_impl.weather, "forecast", lambda lat, lon, days: FORECAST["days"])
    client = FakeClient(script())
    out = tmp_path / "api.json"
    result = run_scenario(str(ROOT / "scenario.json"), str(out), lambda th: TripAgent(client, 10**9), "api")

    failed = [a for a in result["assertions"] if not a["passed"]]
    assert not failed, failed
    assert result["assertions_passed"] == "9/9"
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert len(saved["turns"]) == 7
    first = saved["turns"][0]
    for key in ("tokens", "model_calls", "tools", "cost_usd", "time_s"):
        assert key in first
    assert set(first["tokens"]) == {"input", "cache_read", "cache_write", "output"}
    assert saved["turns"][1]["tools"] == ["get_forecast"]


def test_failed_assertion_is_reported(tmp_path, monkeypatch):
    client = FakeClient([reply(text("ok"))] * 7)  # model never calls tools
    result = run_scenario(str(ROOT / "scenario.json"), str(tmp_path / "r.json"), lambda th: TripAgent(client, 10**9), "api")
    passed = {a["id"]: a["passed"] for a in result["assertions"]}
    assert passed["A1"] is False and passed["A5"] is True  # history was still loaded from disk


def test_loc_counts_every_component():
    api, sdk = loc.api_loc(), loc.sdk_loc()
    for c in loc.COMPONENTS:
        assert api[c] > 0 and sdk[c] > 0
