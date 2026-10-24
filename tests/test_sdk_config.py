"""Offline checks of the SDK configuration and tool wrappers (no Claude Code process is started)."""
import re
from pathlib import Path

from SDK import agent as sdk_agent
from SDK.tools import TOOL_NAMES, TOOLS
from shared import store, tools_impl
from shared.prompts import SYSTEM_PROMPT

SDK_DIR = Path(__file__).resolve().parent.parent / "SDK"
HARNESS = {"loop", "tools", "history", "memory", "context", "compaction", "caching", "tokens"}


def test_options_are_restricted_and_strict():
    o = sdk_agent.build_options()
    assert o.system_prompt == SYSTEM_PROMPT
    assert o.strict_mcp_config is True
    assert o.tools == ["Read"]
    assert set(o.allowed_tools) == set(TOOL_NAMES) | {"Read"}
    assert o.setting_sources == ["project"]
    assert o.model == "claude-opus-5-5" and o.effort == "medium"
    assert o.permission_mode == "dontAsk"


def test_resume_comes_from_disk():
    store.write_json(sdk_agent.SESSION_FILE, {"session_id": "abc-123"})
    a = sdk_agent.SDKTripAgent()
    assert a.session_id == "abc-123" and a.loaded_from_disk == 1
    assert sdk_agent.build_options(resume=a.session_id).resume == "abc-123"


def test_claude_md_holds_only_active_memory():
    tools_impl.remember(key="budget", value="800 NIS")
    tools_impl.remember(key="budget", value="3000 NIS")
    tools_impl.save_itinerary(destination="Eilat", days=["dive"], budget=3000)
    sdk_agent.write_claude_md()
    md = (store.state_dir() / "CLAUDE.md").read_text(encoding="utf-8")
    assert "3000 NIS" in md and "800 NIS" not in md and "Eilat" in md


async def test_tool_wrappers_call_shared_code_and_flag_errors():
    by_name = {t.name: t for t in TOOLS}
    ok = await by_name["remember"].handler({"key": "hiking", "value": "no"})
    assert ok["content"][0]["text"] == '{"saved":"hiking","superseded":null}'
    bad = await by_name["save_itinerary"].handler({"destination": "Haifa", "days": []})
    assert bad["is_error"] is True
    assert [e["tool"] for e in store.read_tool_log()] == ["remember", "save_itinerary"]


def test_every_harness_responsibility_is_marked_replaces():
    marked = set()
    for f in SDK_DIR.glob("*.py"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if m := re.search(r"# replaces: (\w+)", line):
                marked.add(m.group(1))
    assert marked == HARNESS


def test_resumed_session_does_not_double_count_cost():
    store.write_json(sdk_agent.SESSION_FILE, {"session_id": "abc", "total_cost_usd": 0.09})
    assert sdk_agent.SDKTripAgent().cost_so_far == 0.09
