"""Conversation saved to disk, append-only (history.jsonl). Nothing is ever rewritten."""
import json

from API.harness import logger
from shared import store

log = logger(__file__)
FILE = "history.jsonl"


def append(record: dict) -> None:
    """record = {"kind": "message", "message": {...}} or {"kind": "compaction", "summary": "..."}"""
    with open(store.state_dir() / FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_message(message: dict) -> None:
    append({"kind": "message", "message": message})
    log(f"appended {message['role']} message ({len(message['content'])} blocks)")


def load_records() -> list[dict]:
    p = store.state_dir() / FILE
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_active() -> tuple[list[dict], str | None]:
    """Messages after the last compaction, plus that compaction's summary (if any)."""
    records = load_records()
    last = max((i for i, r in enumerate(records) if r["kind"] == "compaction"), default=-1)
    summary = records[last]["summary"] if last >= 0 else None
    messages = [r["message"] for r in records[last + 1:] if r["kind"] == "message"]
    log(f"loaded {len(messages)} active messages from disk ({len(records)} records total, summary={'yes' if summary else 'no'})")
    return messages, summary
