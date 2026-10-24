"""Disk state shared by both harnesses: JSON files under STATE_DIR + an append-only tool log."""
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def state_dir() -> Path:
    """Directory holding all agent state. Set TRIP_STATE_DIR to isolate runs (api / sdk / tests)."""
    d = Path(os.environ.get("TRIP_STATE_DIR", ROOT / "state" / "default"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_json(name: str, default):
    p = state_dir() / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(name: str, data) -> None:
    p = state_dir() / name
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def log_tool(name: str, args: dict, ok: bool, ms: float) -> None:
    """One line per tool call. Assertions read this file, so it works the same for API and SDK."""
    entry = {"ts": time.time(), "tool": name, "args": args, "ok": ok, "ms": round(ms, 1)}
    with open(state_dir() / "tool_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_tool_log() -> list[dict]:
    p = state_dir() / "tool_log.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
