"""Run scenario.json against either agent from a clean state, check assertions, write results JSON."""
import asyncio
import inspect
import json
import shutil
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from shared import loc, store, tools_impl


def reset_state() -> Path:
    d = store.state_dir()
    if store.ROOT / "state" not in d.parents and "pytest" not in str(d):
        raise RuntimeError(f"refusing to delete unexpected state dir: {d}")
    shutil.rmtree(d, ignore_errors=True)
    return store.state_dir()  # recreated empty


@asynccontextmanager
async def _open(agent):
    if hasattr(agent, "__aenter__"):
        async with agent as a:
            yield a
    else:
        yield agent


# ---------- assertions: mostly on saved state, not reply text ----------

def _prefs():
    return store.read_json(tools_impl.MEMORY_FILE, {"preferences": []})["preferences"]


def check(a: dict, ctx: dict) -> tuple[bool, str]:
    t = a["type"]
    if t == "memory_active":
        hits = [p for p in _prefs() if p["status"] == "active" and a["key"] in p["key"] and a["contains"] in p["value"]]
        return bool(hits), json.dumps(hits, ensure_ascii=False)
    if t == "memory_superseded":
        mine = [p for p in _prefs() if a["key"] in p["key"]]
        old = [p for p in mine if p["status"] == "superseded" and a["old"] in p["value"]]
        new = [p for p in mine if p["status"] == "active" and a["new"] in p["value"]]
        return bool(old and new), json.dumps([(p["value"], p["status"]) for p in mine], ensure_ascii=False)
    if t == "tool_by_turn":
        # The agent may fetch data earlier than asked (e.g. weather while planning), so any turn up to N counts.
        called = {n: tools for n, tools in ctx["turn_tools"].items() if n <= a["after_turn"] and a["tool"] in tools}
        return bool(called), f"called in turns {sorted(called)}"
    if t == "trip":
        trips = store.read_json(tools_impl.TRIPS_FILE, [])
        if len(trips) != a["count"]:
            return False, f"{len(trips)} trips"
        tr = trips[a["index"]]
        ok = a["destination"].lower() in tr["destination"].lower() and len(tr["days"]) == a["n_days"]
        return ok, f"{tr['destination']}, {len(tr['days'])} days"
    if t == "loaded_from_disk":
        n = ctx["loaded_from_disk"][a["session"]]
        return n > 0, f"loaded_from_disk={n}"
    if t == "reply_contains_all":
        reply = ctx["replies"][a["after_turn"]].lower()
        missing = [w for w in a["words"] if w.lower() not in reply]
        return not missing, f"missing={missing}"
    raise ValueError(f"unknown assertion type {t}")


# ---------- runner ----------

async def _run(scenario: dict, make_agent, variant: str) -> dict:
    reset_state()
    ctx = {"turn_tools": {}, "replies": {}, "loaded_from_disk": {}}
    turns, results = [], []
    by_turn = {}
    for a in scenario["assertions"]:
        by_turn.setdefault(a["after_turn"], []).append(a)

    for s_idx, session in enumerate(scenario["sessions"], start=1):
        print(f"\n===== session {s_idx}: new agent instance =====", flush=True)
        agent = make_agent(scenario.get("compaction_threshold", 20_000))
        async with _open(agent) as a:
            ctx["loaded_from_disk"][s_idx] = a.loaded_from_disk
            for t in session["turns"]:
                n = t["turn"]
                print(f"\n----- turn {n} -----\nuser> {t['user']}", flush=True)
                log_before = len(store.read_tool_log())
                out = a.chat(t["user"])
                if inspect.isawaitable(out):
                    out = await out
                logged = [e["tool"] for e in store.read_tool_log()[log_before:]]
                ctx["turn_tools"][n] = logged
                ctx["replies"][n] = out["reply"]
                print(f"agent> {out['reply']}", flush=True)
                turns.append({
                    "session": s_idx, "turn": n, "user": t["user"], "reply": out["reply"],
                    "tokens": out["tokens"], "model_calls": out["model_calls"],
                    "tools": logged, "tool_errors": sum(not e["ok"] for e in store.read_tool_log()[log_before:]),
                    "cost_usd": out["cost_usd"], "cache_hit_pct": out["cache_hit_pct"],
                    "time_s": out["time_s"], "compacted": out.get("compacted"),
                })
                for asrt in by_turn.get(n, []):
                    ok, detail = check(asrt, ctx)
                    results.append({"id": asrt["id"], "desc": asrt["desc"], "passed": ok, "detail": detail})
                    print(f"[{'PASS' if ok else 'FAIL'}] {asrt['id']} {asrt['desc']} ({detail})", flush=True)

    totals = {k: sum(t["tokens"][k] for t in turns) for k in ("input", "cache_read", "cache_write", "output")}
    total_in = totals["input"] + totals["cache_read"] + totals["cache_write"]
    return {
        "variant": variant,
        "scenario": scenario["name"],
        "model": "claude-opus-5-5",
        "effort": "medium",
        "versions": {p: version(p) for p in ("anthropic", "claude-agent-sdk")},
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "turns": turns,
        "totals": {
            "tokens": totals,
            "cache_hit_pct": round(100 * totals["cache_read"] / total_in, 1) if total_in else 0.0,
            "model_calls": sum(t["model_calls"] for t in turns),
            "cost_usd": round(sum(t["cost_usd"] for t in turns), 6),
            "time_s": round(sum(t["time_s"] for t in turns), 2),
        },
        "assertions": results,
        "assertions_passed": f"{sum(r['passed'] for r in results)}/{len(results)}",
        "loc": loc.api_loc() if variant == "api" else loc.sdk_loc(),
    }


def run_scenario(scenario_path: str, out_path: str, make_agent, variant: str) -> dict:
    scenario = json.loads(Path(scenario_path).read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    result = asyncio.run(_run(scenario, make_agent, variant))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{variant}: assertions {result['assertions_passed']}, cost ${result['totals']['cost_usd']:.4f}, "
          f"{time.perf_counter() - t0:.0f}s -> {out_path}", flush=True)
    return result
