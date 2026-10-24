"""Summarize the whole conversation once it passes a token threshold.

Simple compaction: one summary replaces everything; the next request starts from the summary
plus the new user turn and replays nothing else (no old thinking blocks), so the API's
history-binding check stays valid. Runs only between turns, never mid tool round.
"""
from API.harness import history, logger

log = logger(__file__)

SUMMARY_PROMPT = (
    "Summarize this conversation for your own future use. Keep: destinations discussed, saved "
    "itineraries, weather facts, user preferences and any changes to them, open requests. "
    "Under 200 words, bullet points. Do not call any tools."
)


def should_compact(context_tokens: int, threshold: int) -> bool:
    hit = context_tokens >= threshold
    log(f"context {context_tokens} tokens vs threshold {threshold} -> {'COMPACT' if hit else 'keep'}")
    return hit


def compact(call_model, messages: list[dict]) -> str:
    """call_model(messages) -> Message. Same system/tools as the session, so the prefix stays cached."""
    request = messages + [{"role": "user", "content": [{"type": "text", "text": SUMMARY_PROMPT}]}]
    resp = call_model(request)
    summary = "".join(b.text for b in resp.content if b.type == "text").strip()
    history.append({"kind": "compaction", "summary": summary, "replaced_messages": len(messages)})
    log(f"summarized {len(messages)} messages into {len(summary)} chars")
    return summary
