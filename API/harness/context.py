"""What enters each turn.

- system + tools: frozen for the whole session (cacheable, and required unchanged for replayed thinking).
- the new user message carries the per-turn context: a compaction summary (if any) and only the
  relevant memory lines, before the user's text. This keeps history append-only.
"""
from API.harness import logger

log = logger(__file__)


def build_user_turn(user_text: str, memory_block: str | None, summary: str | None = None) -> dict:
    blocks = []
    if summary:
        blocks.append({"type": "text", "text": f"<conversation_summary>\n{summary}\n</conversation_summary>"})
    if memory_block:
        blocks.append({"type": "text", "text": f"<memory>\n{memory_block}\n</memory>"})
    blocks.append({"type": "text", "text": user_text})
    log(f"user turn: summary={'yes' if summary else 'no'}, memory={'yes' if memory_block else 'no'}, "
        f"~{sum(len(b['text']) for b in blocks) // 4} tokens")
    return {"role": "user", "content": blocks}
