# Trip Planner: One Agent, Two Harnesses

A weekend trip-planning agent, built twice with the same tools, prompt and scenario:

| | `API/` | `SDK/` |
|---|---|---|
| Runs on | Raw Claude Messages API | Claude Agent SDK (Claude Code) |
| Harness | Written by hand, one file per responsibility | Configured, lines marked `# replaces: <name>` |
| Auth | `ANTHROPIC_API_KEY` from the Claude Console | Your Claude Code login (no key) |

**Results:** both versions pass 9/9 assertions at about the same cost ($0.152 vs $0.155). The SDK version is 2.6x less code.
Full comparison: [REPORT.md](REPORT.md) and the interactive dashboard [docs/index.html](docs/index.html).

Authors: Leah & Yehudit

## What the agent does

It plans weekend trips. It checks the real weather forecast, builds and saves day-by-day itineraries, makes packing
lists, and remembers your preferences across sessions. When you contradict a saved preference ("budget 800" and
later "budget 3000"), it says so, updates the preference, and keeps the old one as history.

| Requirement | How it is met |
|---|---|
| **Tools** (3+, one external) | `geocode` and `get_forecast` (external: [Open-Meteo](https://open-meteo.com), free, no key), `save_itinerary`, `packing_list`, `remember`, `recall` |
| **Memory** | `memory.json` holds preferences with history (`active` / `superseded`). `trips.json` holds saved itineraries. |
| **Context engineering** | API: `context.py` adds only the memory lines relevant to the current message, so a weather question gets none. SDK: a generated `CLAUDE.md` with active preferences only. |
| **Token optimization** | Tool outputs are compacted (5 numbers per forecast day instead of the raw payload; minified JSON). Tokens, cache hits and cost are recorded for every turn. |

## Project layout

```
shared/              domain code used by both versions
  tools_impl.py      the 6 tools (plain Python) + tool-call log
  weather.py         Open-Meteo client, compact output
  store.py           JSON state under TRIP_STATE_DIR
  prompts.py         the single system prompt
  scenario_runner.py runs scenario.json from a clean state, checks assertions, writes results
  loc.py             lines of code per harness component
API/
  main.py  agent.py
  harness/  loop.py tools.py history.py memory.py context.py compaction.py caching.py tokens.py
SDK/
  main.py  agent.py  tools.py
tests/               offline tests with a mock client, no API key needed
scenario.json        7 turns, 2 sessions, 9 assertions
results/             api.json, sdk.json (per-turn tokens, calls, tools, cost, time, assertions, LOC)
scripts/build_report.py   builds REPORT.md + docs/index.html from results/
```

Every runtime action in the API version is printed with the file that ran it:

```
[memory.py] retrieve: 2/2 preferences, last_trip=yes
[context.py] user turn: summary=no, memory=yes, ~61 tokens
[caching.py] 3 breakpoints: tools[5], system, messages[8]
[tokens.py] call #1: in=4 cache_read=4445 cache_write=328 out=242 $0.00739
[loop.py] model call #1 stop_reason=end_turn
```

## Setup

Python 3.14 (Windows). All library versions are locked in `requirements.txt`.

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

```powershell
# Offline tests (no key, no network)
.venv\Scripts\python -m pytest

# API version: set the key in this terminal only, never in code or git
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.venv\Scripts\python API\main.py --scenario scenario.json --out results\api.json
Remove-Item Env:ANTHROPIC_API_KEY

# SDK version: uses your Claude Code login; refuses to run if ANTHROPIC_API_KEY is set
.venv\Scripts\python SDK\main.py --scenario scenario.json --out results\sdk.json

# Rebuild REPORT.md and docs/index.html
.venv\Scripts\python scripts\build_report.py
```

Run `API\main.py` or `SDK\main.py` without `--scenario` to chat with the agent interactively.

## Comparison rules we followed

- Same model and effort in both: `claude-opus-5-5`, `medium`.
- Locked library versions (`anthropic==2.3.0`, `claude-agent-sdk==0.2.174`).
- Every scenario run deletes `state/<api|sdk>/` first. Session 2 runs on a new agent instance that loads everything from disk.
- SDK settings: our own system prompt, a restricted tool list (`tools=["Read"]` + our 6 MCP tools), `strict_mcp_config=True`, `permission_mode="dontAsk"`.

## Notes

- `shared/__init__.py` makes Python trust the Windows certificate store (`truststore`), so HTTPS works behind
  filtering proxies. Certificate verification stays on.
- `claude-opus-5-5` checks that the system prompt, the tools and earlier messages are unchanged before it reuses
  earlier thinking. That is why the API harness never edits its system prompt, injects memory into the user turn
  instead, and uses "simple" compaction (one summary replaces everything).
