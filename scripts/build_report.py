"""Build REPORT.md and docs/index.html from results/api.json + results/sdk.json."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMP = ["loop", "tools", "history", "memory", "context", "compaction", "caching", "tokens"]


def load(v):
    r = json.loads((ROOT / "results" / f"{v}.json").read_text(encoding="utf-8"))
    r["harness_loc"] = sum(r["loc"][c] for c in COMP)
    return r


def in_tok(t):
    return t["input"] + t["cache_read"] + t["cache_write"]


A, S = load("api"), load("sdk")
TA, TS = A["totals"], S["totals"]
ia, is_ = in_tok(TA["tokens"]), in_tok(TS["tokens"])
turn = {v: {t["turn"]: t for t in r["turns"]} for v, r in (("api", A), ("sdk", S))}
t2a, t2s = in_tok(turn["api"][2]["tokens"]), in_tok(turn["sdk"][2]["tokens"])
t5a, t5s = turn["api"][5], turn["sdk"][5]
t7a, t7s = turn["api"][7], turn["sdk"][7]
compacted = [t["turn"] for t in A["turns"] if t["compacted"]]
sdk_total_loc = S["loc"]["agent.py + main.py + tools.py (total)"]
api_total_loc = A["harness_loc"] + A["loc"]["agent.py + main.py"]

TABLE = [
    ["Input-side tokens (input + cache read + cache write)", f"{ia:,}", f"{is_:,}"],
    ["  of which fresh input", f"{TA['tokens']['input']:,}", f"{TS['tokens']['input']:,}"],
    ["  of which cache read", f"{TA['tokens']['cache_read']:,}", f"{TS['tokens']['cache_read']:,}"],
    ["  of which cache write", f"{TA['tokens']['cache_write']:,}", f"{TS['tokens']['cache_write']:,}"],
    ["Output tokens", f"{TA['tokens']['output']:,}", f"{TS['tokens']['output']:,}"],
    ["Cache hit %", f"{TA['cache_hit_pct']}%", f"{TS['cache_hit_pct']}%"],
    ["Model calls", str(TA["model_calls"]), str(TS["model_calls"])],
    ["Cost (USD)", f"${TA['cost_usd']:.4f}", f"${TS['cost_usd']:.4f}"],
    ["Wall time", f"{TA['time_s']:.0f}s", f"{TS['time_s']:.0f}s"],
    ["Assertions passed", A["assertions_passed"], S["assertions_passed"]],
    ["Harness lines of code", str(A["harness_loc"]), str(sum(S["loc"][c] for c in COMP))],
    ["All agent code (incl. agent.py, main.py)", str(api_total_loc), str(sdk_total_loc)],
]

FINDINGS = [
    {"title": "Where the SDK used more tokens", "points": [
        f"<b>Every call is heavier.</b> Turn 2 is a single call with no tools in both versions: {t2a:,} input-side tokens "
        f"on the API vs {t2s:,} on the SDK (+{t2s - t2a:,}). Claude Code adds its own context (environment info, the Read "
        f"tool, MCP tool wrappers, CLAUDE.md) on top of our system prompt. Over the run that is {is_:,} vs {ia:,} "
        f"input-side tokens (+{100 * (is_ - ia) / ia:.0f}%).",
        f"<b>Memory costs an extra round trip.</b> In turn 5 (\"what do you remember?\") the API injected the relevant "
        f"memory into the user turn and answered in {t5a['model_calls']} call. The SDK called "
        f"<code>{', '.join(t5s['tools']) or 'no tool'}</code> and needed {t5s['model_calls']} calls, because CLAUDE.md is "
        f"loaded once per session and the model chose to double-check.",
        "<b>Cache writes cost more.</b> Claude Code writes 1-hour cache entries ($8/M, 2x input), and our API harness "
        "writes 5-minute entries ($5/M, 1.25x).",
    ]},
    {"title": "Where the SDK used fewer", "points": [
        f"<b>Higher cache hit rate:</b> {TS['cache_hit_pct']}% vs {TA['cache_hit_pct']}%. Its larger, stable prefix is "
        f"cached, and the 1-hour TTL even survived between our runs. Turn 1 already read "
        f"{turn['sdk'][1]['tokens']['cache_read']:,} tokens from cache.",
        f"<b>No early compaction.</b> We set the API threshold low ({json.loads((ROOT / 'scenario.json').read_text(encoding='utf-8'))['compaction_threshold']:,} tokens) "
        f"so compaction would run inside the scenario. It fired in turn {', '.join(map(str, compacted)) or '-'}: one extra "
        f"summary call and a cache reset, ${t7a['cost_usd']:.4f} vs ${t7s['cost_usd']:.4f} on the SDK. Claude Code only "
        "compacts near the context limit.",
        f"<b>Fewer output tokens</b> ({TS['tokens']['output']:,} vs {TA['tokens']['output']:,}) and a shorter wall time "
        f"({TS['time_s']:.0f}s vs {TA['time_s']:.0f}s) on this run. That is within normal run-to-run variance, not a "
        "structural win.",
        f"<b>Net cost is a wash:</b> ${TA['cost_usd']:.4f} (API) vs ${TS['cost_usd']:.4f} (SDK). The SDK sends "
        f"{100 * (is_ - ia) / ia:.0f}% more tokens, but most of them are cheap cache reads.",
    ]},
    {"title": "Control we had in the API and lost in the SDK", "points": [
        "<b>What enters each turn.</b> context.py puts only the memory lines relevant to <i>this</i> message into the user "
        "turn (none for a weather question). In the SDK, memory is CLAUDE.md, written once per session. After the "
        "contradiction in turn 6 it stays stale until the next session, and Claude Code adds context we can't see.",
        "<b>Cache placement and TTL.</b> We chose 3 breakpoints and the 5-minute TTL. The SDK decides both.",
        "<b>Compaction policy.</b> We set the threshold, the summary prompt and the shape: simple compaction, which is "
        "required because Opus 5.5 rejects edited history under replayed thinking blocks. The SDK's is automatic and opaque.",
        "<b>History and metering.</b> Our history.jsonl lives in our state dir and we see the usage of every single call. "
        "The SDK keeps the transcript under ~/.claude, reports usage per query, and <code>total_cost_usd</code> keeps "
        "counting across <code>resume</code>. We double-counted session 1 until we persisted the running total.",
    ]},
    {"title": "What the SDK gave us for free", "points": [
        f"<b>{api_total_loc / max(sdk_total_loc, 1):.1f}x less code:</b> {sdk_total_loc} lines for the whole SDK agent vs "
        f"{api_total_loc} for the API agent. Each of the 8 harness files collapses into 1-4 config lines.",
        "<b>No API key or per-token bill</b> for personal use. It runs on the Claude Code login.",
        "<b>Things we did not have to learn the hard way:</b> the loop, parallel tool_results, is_error, thinking-block "
        "replay rules, cache breakpoints and session persistence all come built in.",
    ]},
]

VERDICT = {
    "title": "Our pick for this agent: the SDK",
    "body": [
        f"Both versions passed {A['assertions_passed']} checks at practically the same cost, and the SDK version is a "
        f"fraction of the code. A personal trip planner is a low-volume tool, and running on our Claude Code login without "
        f"a key is a real advantage.",
        "We would switch to the API harness if this became a product: many users, where the per-call token overhead and "
        "the extra memory round trip add up, or where we need exact control over what memory each turn sees, cache "
        "policy, and per-call cost accounting.",
    ],
}


def md(s: str) -> str:
    s = re.sub(r"</?b>", "**", s)
    s = re.sub(r"</?i>", "*", s)
    return re.sub(r"</?code>", "`", s)


def build_markdown() -> str:
    out = ["# Report: Trip Planner, API vs SDK", "",
           f"Same agent, tools and scenario (`scenario.json`: 7 turns, 2 sessions) on `{A['model']}` with effort "
           f"`{A['effort']}`. Every run starts from a clean state. Library versions: "
           + ", ".join(f"`{k}=={v}`" for k, v in A["versions"].items()) + ".", "",
           "Interactive version of this report: `docs/index.html`.", "",
           "## Results", "", "| Metric | API | SDK |", "|---|---:|---:|"]
    out += [f"| {r[0].strip()} | {r[1]} | {r[2]} |" for r in TABLE]
    out += ["", "## Per turn", "",
            "| Turn | Session | API tools | API calls | API tokens in/out | API cost | SDK tools | SDK calls | SDK tokens in/out | SDK cost |",
            "|---:|---:|---|---:|---:|---:|---|---:|---:|---:|"]
    for a, s in zip(A["turns"], S["turns"]):
        tools = lambda t: ", ".join(t["tools"]) or "-"
        flag = " (compacted)" if a["compacted"] else ""
        out.append(f"| {a['turn']} | {a['session']} | {tools(a)}{flag} | {a['model_calls']} | {in_tok(a['tokens']):,}/{a['tokens']['output']:,} "
                   f"| ${a['cost_usd']:.4f} | {tools(s)} | {s['model_calls']} | {in_tok(s['tokens']):,}/{s['tokens']['output']:,} | ${s['cost_usd']:.4f} |")
    out += ["", "## Lines of code per harness component", "",
            "API counts non-blank, non-comment lines in `API/harness/<name>.py`. SDK counts lines marked `# replaces: <name>`.", "",
            "| Component | API | SDK |", "|---|---:|---:|"]
    out += [f"| {c} | {A['loc'][c]} | {S['loc'][c]} |" for c in COMP]
    out += [f"| **harness total** | **{A['harness_loc']}** | **{sum(S['loc'][c] for c in COMP)}** |",
            f"| all agent code | {api_total_loc} | {sdk_total_loc} |"]
    out += ["", "## Assertions", "", "| ID | Check | API | SDK |", "|---|---|:-:|:-:|"]
    out += [f"| {a['id']} | {a['desc']} | {'PASS' if a['passed'] else 'FAIL'} | {'PASS' if s['passed'] else 'FAIL'} |"
            for a, s in zip(A["assertions"], S["assertions"])]
    for f in FINDINGS:
        out += ["", f"## {f['title']}", ""] + [f"- {md(p)}" for p in f["points"]]
    out += ["", f"## {VERDICT['title']}", ""] + [md(p) + "\n" for p in VERDICT["body"]]
    out += ["## Notes on the runs", "",
            "- The first runs scored 8/9 in both versions. A3 required the weather tool in turn 2 exactly, but both agents "
            "had already fetched the forecast in turn 1 while planning. That was a bug in our assertion, not the agents, so "
            "A3 now checks \"called by turn 2\".",
            "- The first SDK run also over-reported cost, because `total_cost_usd` includes the resumed session's earlier "
            "spend. Fixed by persisting the running total. Both versions were then re-run from a clean state.", ""]
    return "\n".join(out)


def main():
    (ROOT / "REPORT.md").write_text(build_markdown(), encoding="utf-8")
    data = {"api": A, "sdk": S, "table": [[r[0], r[1], r[2]] for r in TABLE], "findings": FINDINGS, "verdict": VERDICT}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = (ROOT / "scripts" / "report_template.html").read_text(encoding="utf-8").replace("/*DATA*/", blob)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "index.html").write_text(html, encoding="utf-8")
    print("wrote REPORT.md and docs/index.html")


if __name__ == "__main__":
    main()
