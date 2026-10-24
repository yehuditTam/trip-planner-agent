"""Offline tests for every API/harness component, using a scripted mock client (no API key)."""
import json

import pytest

from API.agent import TripAgent
from API.harness import caching, compaction, context, history, memory, tokens
from API.harness.tools import TOOLS, dispatch
from shared import store, tools_impl
from tests.fakes import FakeClient, reply, text, tool_use


def test_loop_returns_all_tool_results_in_one_message():
    client = FakeClient([
        reply(tool_use("remember", key="budget", value="800 NIS"), tool_use("remember", key="hiking", value="no long hikes")),
        reply(text("Saved both.")),
    ])
    out = TripAgent(client).chat("Budget 800 and no long hikes, remember that")
    assert out["reply"] == "Saved both."
    assert out["tools"] == ["remember", "remember"]
    assert out["model_calls"] == 2
    second_request = client.messages.calls[1]["messages"]
    results_msg = second_request[-1]
    assert results_msg["role"] == "user"
    assert [b["type"] for b in results_msg["content"]] == ["tool_result", "tool_result"]


def test_loop_stops_when_stop_reason_is_not_tool_use():
    client = FakeClient([reply(text("Hi!"))])
    out = TripAgent(client).chat("hello")
    assert out["model_calls"] == 1 and out["tools"] == []


def test_tool_error_is_returned_as_is_error():
    block = type("B", (), {"id": "t1", "name": "save_itinerary", "input": {"destination": "Haifa", "days": []}})
    result = dispatch(block)
    assert result["is_error"] is True and "days" in result["content"]
    unknown = dispatch(type("B", (), {"id": "t2", "name": "nope", "input": {}}))
    assert unknown["is_error"] is True


def test_tool_output_is_compact_json():
    tools_impl.remember(key="budget", value="800 NIS")
    block = type("B", (), {"id": "t1", "name": "recall", "input": {"query": ""}})
    content = dispatch(block)["content"]
    assert ", " not in content and json.loads(content)["preferences"][0]["key"] == "budget"


def test_every_schema_has_an_implementation():
    assert {t["name"] for t in TOOLS} == {"geocode", "get_forecast", "save_itinerary", "packing_list", "remember", "recall"}


def test_history_is_append_only_and_reloaded_by_new_instance():
    TripAgent(FakeClient([reply(text("one"))])).chat("first")
    size_before = (store.state_dir() / history.FILE).stat().st_size
    lines_before = (store.state_dir() / history.FILE).read_text(encoding="utf-8")
    TripAgent(FakeClient([reply(text("two"))])).chat("second")
    lines_after = (store.state_dir() / history.FILE).read_text(encoding="utf-8")
    assert lines_after.startswith(lines_before) and len(lines_after) > size_before
    agent3 = TripAgent(FakeClient([]))
    assert agent3.loaded_from_disk == 4  # user, assistant, user, assistant


def test_thinking_blocks_are_replayed_unchanged():
    client = FakeClient([reply(text("one")), reply(text("two"))])
    agent = TripAgent(client)
    agent.chat("first")
    agent.chat("second")
    replayed = client.messages.calls[1]["messages"][1]["content"][0]
    assert replayed == {"type": "thinking", "thinking": "", "signature": "sig"}


def test_memory_retrieves_only_relevant_preferences():
    tools_impl.remember(key="budget", value="800 NIS")
    tools_impl.remember(key="hiking", value="dislikes long hikes")
    assert memory.retrieve("What's the weather tomorrow?") is None
    only_budget = memory.retrieve("Is that too expensive?")
    assert "budget" in only_budget and "hiking" not in only_budget
    tools_impl.save_itinerary(destination="Haifa", days=["a"], budget=800)
    everything = memory.retrieve("What do you remember about me?")
    assert "hiking" in everything and "Haifa" in everything


def test_context_puts_memory_in_user_turn_not_system():
    tools_impl.remember(key="budget", value="800 NIS")
    client = FakeClient([reply(text("ok")), reply(text("ok"))])
    agent = TripAgent(client)
    agent.chat("plan a trip")
    agent.chat("weather?")
    first, second = client.messages.calls
    assert first["system"] == second["system"]  # frozen system prompt
    assert "800 NIS" in json.dumps(first["messages"][-1])
    assert "<memory>" not in second["messages"][-1]["content"][0]["text"]


def test_build_user_turn_order():
    msg = context.build_user_turn("hi", "mem", "sum")
    assert [b["text"][:5] for b in msg["content"]] == ["<conv", "<memo", "hi"]


def test_cache_breakpoints_on_copy_only():
    msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    system, tools, sent = caching.apply("SYS", TOOLS, msgs)
    assert "cache_control" in tools[-1] and "cache_control" in system[0]
    assert "cache_control" in sent[-1]["content"][-1]
    assert "cache_control" not in msgs[-1]["content"][-1] and "cache_control" not in TOOLS[-1]


def test_cost_calculation():
    u = {"input": 1_000_000, "output": 1_000_000, "cache_write": 1_000_000, "cache_read": 1_000_000}
    assert tokens.cost("claude-opus-5-5", u) == pytest.approx(4 + 20 + 5 + 0.2)


def test_turn_meter_reports_cache_hit_and_cost():
    client = FakeClient([reply(tool_use("recall", query=""), inp=100, write=900), reply(text("ok"), inp=50, read=900)])
    out = TripAgent(client).chat("hi")
    assert out["tokens"] == {"input": 150, "cache_read": 900, "cache_write": 900, "output": 40}
    assert out["cache_hit_pct"] == pytest.approx(46.2, abs=0.1)
    assert out["cost_usd"] > 0


def test_compaction_triggers_above_threshold_and_starts_fresh():
    client = FakeClient([
        reply(text("first answer"), inp=5000),
        reply(text("- user likes Haifa"), inp=10),  # the summary call
        reply(text("second answer"), inp=10),
    ])
    agent = TripAgent(client, compaction_threshold=1000)
    agent.chat("first")
    out = agent.chat("second")
    assert out["compacted"] is True and out["model_calls"] == 2
    after = client.messages.calls[2]["messages"]
    assert len(after) == 1  # only the new user turn: nothing old replayed
    assert "<conversation_summary>" in after[0]["content"][0]["text"]
    records = history.load_records()
    assert any(r["kind"] == "compaction" for r in records)
    assert TripAgent(FakeClient([])).summary == "- user likes Haifa"


def test_no_compaction_below_threshold():
    assert compaction.should_compact(500, 1000) is False


def test_effort_and_model_are_sent():
    client = FakeClient([reply(text("ok"))])
    TripAgent(client).chat("hi")
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["output_config"] == {"effort": "medium"}
