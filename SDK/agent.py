"""TripAgent on the Claude Agent SDK: Claude Code runs the harness, we only configure it."""
import json
import time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, ToolUseBlock

from SDK.tools import SERVER, TOOL_NAMES
from shared import store, tools_impl
from shared.prompts import SYSTEM_PROMPT

MODEL = "claude-opus-5-5"
EFFORT = "medium"
SESSION_FILE = "sdk_session.json"


def write_claude_md() -> None:
    """Project memory Claude Code loads at session start: only active preferences + last trip."""
    lines = [f"- {p['key']}: {p['value']}" for p in tools_impl.active_preferences()]  # replaces: memory
    if (trip := tools_impl.last_trip_summary()):
        lines.append(f"- last trip: {trip}")
    body = "\n".join(lines) or "- (nothing saved yet)"
    (store.state_dir() / "CLAUDE.md").write_text(f"# Saved user memory\n{body}\n", encoding="utf-8")  # replaces: memory


def build_options(resume: str | None = None) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,                 # own prompt instead of Claude Code's default
        model=MODEL,
        effort=EFFORT,
        mcp_servers={"trip": SERVER},                # replaces: tools
        strict_mcp_config=True,                      # ignore any other MCP config on this machine
        tools=["Read"],                              # only built-in tool available: Read
        allowed_tools=[*TOOL_NAMES, "Read"],         # restricted tool list, auto-approved
        permission_mode="dontAsk",                   # anything not allowed is denied, never prompted
        setting_sources=["project"],                 # replaces: memory (loads CLAUDE.md from cwd)
        cwd=str(store.state_dir()),                  # replaces: context (Claude Code adds cwd, CLAUDE.md, env info)
        resume=resume,                               # replaces: history
        # replaces: compaction - automatic in Claude Code
        # replaces: caching - automatic in Claude Code
    )


class SDKTripAgent:
    """async with SDKTripAgent() as agent: await agent.chat("...")"""

    def __init__(self):
        saved = store.read_json(SESSION_FILE, {})
        self.session_id = saved.get("session_id")              # replaces: history (load from disk)
        self.loaded_from_disk = 1 if self.session_id else 0
        # total_cost_usd keeps counting across resume, so the running total is persisted with the session.
        self.cost_so_far = saved.get("total_cost_usd", 0.0)

    async def __aenter__(self):
        write_claude_md()
        self.client = ClaudeSDKClient(build_options(resume=self.session_id))
        await self.client.connect()
        return self

    async def __aexit__(self, *exc):
        await self.client.disconnect()

    async def chat(self, user_text: str) -> dict:
        t0 = time.perf_counter()
        await self.client.query(user_text)                      # replaces: loop
        tools, message_ids, reply, result = [], set(), "", None
        async for msg in self.client.receive_response():        # replaces: loop
            if isinstance(msg, AssistantMessage):
                message_ids.add(msg.message_id)
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        tools.append(block.name.removeprefix("mcp__trip__"))
            elif isinstance(msg, ResultMessage):
                result = msg
        reply = result.result or ""
        self.session_id = result.session_id
        store.write_json(SESSION_FILE, {"session_id": self.session_id,  # replaces: history (save to disk)
                                        "total_cost_usd": result.total_cost_usd or 0.0})

        u = result.usage or {}                                  # replaces: tokens
        usage = {
            "input": u.get("input_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0),
            "cache_write": u.get("cache_creation_input_tokens", 0),
            "output": u.get("output_tokens", 0),
        }
        total_in = usage["input"] + usage["cache_read"] + usage["cache_write"]
        # total_cost_usd is cumulative for the client session; per-turn cost is the delta.
        cost = (result.total_cost_usd or 0.0) - self.cost_so_far  # replaces: tokens
        self.cost_so_far = result.total_cost_usd or 0.0
        return {
            "reply": reply, "tools": tools, "compacted": None,
            "time_s": round(time.perf_counter() - t0, 2),
            "tokens": usage, "model_calls": len(message_ids),
            "cost_usd": round(cost, 6),
            "cache_hit_pct": round(100 * usage["cache_read"] / total_in, 1) if total_in else 0.0,
            "num_turns": result.num_turns, "session_id": result.session_id,
        }
