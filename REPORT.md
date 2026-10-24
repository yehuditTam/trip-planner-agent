# Report: Trip Planner, API vs SDK

Same agent, tools and scenario (`scenario.json`: 7 turns, 2 sessions) on `claude-opus-5-5` with effort `medium`. Every run starts from a clean state. Library versions: `anthropic==2.3.0`, `claude-agent-sdk==0.2.174`.

Interactive version of this report: `docs/index.html`.

## Results

| Metric | API | SDK |
|---|---:|---:|
| Input-side tokens (input + cache read + cache write) | 56,677 | 90,377 |
| of which fresh input | 46 | 30 |
| of which cache read | 49,909 | 84,589 |
| of which cache write | 6,722 | 5,758 |
| Output tokens | 5,414 | 4,570 |
| Cache hit % | 88.1% | 93.6% |
| Model calls | 15 | 15 |
| Cost (USD) | $0.1521 | $0.1546 |
| Wall time | 69s | 57s |
| Assertions passed | 9/9 | 9/9 |
| Harness lines of code | 264 | 17 |
| All agent code (incl. agent.py, main.py) | 343 | 133 |

## Per turn

| Turn | Session | API tools | API calls | API tokens in/out | API cost | SDK tools | SDK calls | SDK tokens in/out | SDK cost |
|---:|---:|---|---:|---:|---:|---|---:|---:|---:|
| 1 | 1 | remember, remember, geocode, get_forecast | 3 | 5,422/736 | $0.0193 | remember, remember, geocode, get_forecast | 3 | 10,160/803 | $0.0215 |
| 2 | 1 | - | 1 | 2,650/256 | $0.0079 | - | 1 | 4,334/262 | $0.0103 |
| 3 | 1 | save_itinerary | 2 | 6,553/1,130 | $0.0284 | save_itinerary | 2 | 9,997/1,152 | $0.0330 |
| 4 | 1 | packing_list | 2 | 8,684/399 | $0.0139 | packing_list | 2 | 12,041/411 | $0.0168 |
| 5 | 2 | - | 1 | 4,777/242 | $0.0074 | recall | 2 | 13,384/220 | $0.0121 |
| 6 | 2 | remember, remember, geocode, get_forecast | 3 | 16,895/1,377 | $0.0372 | remember, remember, geocode, get_forecast | 3 | 22,610/1,164 | $0.0375 |
| 7 | 2 | save_itinerary (compacted) | 3 | 11,696/1,274 | $0.0379 | save_itinerary | 2 | 17,851/558 | $0.0235 |

## Lines of code per harness component

API counts non-blank, non-comment lines in `API/harness/<name>.py`. SDK counts lines marked `# replaces: <name>`.

| Component | API | SDK |
|---|---:|---:|
| loop | 31 | 2 |
| tools | 96 | 4 |
| history | 23 | 3 |
| memory | 29 | 3 |
| context | 12 | 1 |
| compaction | 18 | 1 |
| caching | 15 | 1 |
| tokens | 40 | 2 |
| **harness total** | **264** | **17** |
| all agent code | 343 | 133 |

## Assertions

| ID | Check | API | SDK |
|---|---|:-:|:-:|
| A1 | Budget 800 saved as an active preference | PASS | PASS |
| A2 | Hiking preference saved | PASS | PASS |
| A3 | External weather tool (Open-Meteo) called by the weather question | PASS | PASS |
| A4 | Haifa itinerary with 2 days saved to trips.json | PASS | PASS |
| A5 | Session 2 is a new instance that loaded state from disk | PASS | PASS |
| A6 | Session 2 recalls the last trip and the budget | PASS | PASS |
| A7 | Contradiction: budget 3000 active, 800 kept as superseded | PASS | PASS |
| A8 | Contradiction: hiking preference updated, old one kept as superseded | PASS | PASS |
| A9 | Second trip (Eilat) appended, first one kept | PASS | PASS |

## Where the SDK used more tokens

- **Every call is heavier.** Turn 2 is a single call with no tools in both versions: 2,650 input-side tokens on the API vs 4,334 on the SDK (+1,684). Claude Code adds its own context (environment info, the Read tool, MCP tool wrappers, CLAUDE.md) on top of our system prompt. Over the run that is 90,377 vs 56,677 input-side tokens (+59%).
- **Memory costs an extra round trip.** In turn 5 ("what do you remember?") the API injected the relevant memory into the user turn and answered in 1 call. The SDK called `recall` and needed 2 calls, because CLAUDE.md is loaded once per session and the model chose to double-check.
- **Cache writes cost more.** Claude Code writes 1-hour cache entries ($8/M, 2x input), and our API harness writes 5-minute entries ($5/M, 1.25x).

## Where the SDK used fewer

- **Higher cache hit rate:** 93.6% vs 88.1%. Its larger, stable prefix is cached, and the 1-hour TTL even survived between our runs. Turn 1 already read 9,731 tokens from cache.
- **No early compaction.** We set the API threshold low (5,000 tokens) so compaction would run inside the scenario. It fired in turn 7: one extra summary call and a cache reset, $0.0379 vs $0.0235 on the SDK. Claude Code only compacts near the context limit.
- **Fewer output tokens** (4,570 vs 5,414) and a shorter wall time (57s vs 69s) on this run. That is within normal run-to-run variance, not a structural win.
- **Net cost is a wash:** $0.1521 (API) vs $0.1546 (SDK). The SDK sends 59% more tokens, but most of them are cheap cache reads.

## Control we had in the API and lost in the SDK

- **What enters each turn.** context.py puts only the memory lines relevant to *this* message into the user turn (none for a weather question). In the SDK, memory is CLAUDE.md, written once per session. After the contradiction in turn 6 it stays stale until the next session, and Claude Code adds context we can't see.
- **Cache placement and TTL.** We chose 3 breakpoints and the 5-minute TTL. The SDK decides both.
- **Compaction policy.** We set the threshold, the summary prompt and the shape: simple compaction, which is required because Opus 5.5 rejects edited history under replayed thinking blocks. The SDK's is automatic and opaque.
- **History and metering.** Our history.jsonl lives in our state dir and we see the usage of every single call. The SDK keeps the transcript under ~/.claude, reports usage per query, and `total_cost_usd` keeps counting across `resume`. We double-counted session 1 until we persisted the running total.

## What the SDK gave us for free

- **2.6x less code:** 133 lines for the whole SDK agent vs 343 for the API agent. Each of the 8 harness files collapses into 1-4 config lines.
- **No API key or per-token bill** for personal use. It runs on the Claude Code login.
- **Things we did not have to learn the hard way:** the loop, parallel tool_results, is_error, thinking-block replay rules, cache breakpoints and session persistence all come built in.

## Our pick for this agent: the SDK

Both versions passed 9/9 checks at practically the same cost, and the SDK version is a fraction of the code. A personal trip planner is a low-volume tool, and running on our Claude Code login without a key is a real advantage.

We would switch to the API harness if this became a product: many users, where the per-call token overhead and the extra memory round trip add up, or where we need exact control over what memory each turn sees, cache policy, and per-call cost accounting.

## Notes on the runs

- The first runs scored 8/9 in both versions. A3 required the weather tool in turn 2 exactly, but both agents had already fetched the forecast in turn 1 while planning. That was a bug in our assertion, not the agents, so A3 now checks "called by turn 2".
- The first SDK run also over-reported cost, because `total_cost_usd` includes the resumed session's earlier spend. Fixed by persisting the running total. Both versions were then re-run from a clean state.
